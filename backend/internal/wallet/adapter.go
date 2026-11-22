package wallet

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/google/uuid"
)

var (
	ErrInvalidSignature    = errors.New("payment verification failed: invalid signature or HMAC")
	ErrMalformedPayload    = errors.New("payment verification failed: malformed payload")
	ErrPaymentRejected     = errors.New("payment transaction was rejected by external provider")
	ErrDuplicateCallback   = errors.New("payment transaction callback already verified")
	ErrUnsupportedCurrency = errors.New("payment provider only supports PKR currency")
)

// VerifiedPayment represents the normalized internal financial record produced by any PaymentGateway adapter.
type VerifiedPayment struct {
	ProviderReference string            `json:"providerReference"` // e.g. "T20261122150001"
	UserID            uuid.UUID         `json:"userId"`
	AmountPKR         int64             `json:"amountPkr"`
	Status            string            `json:"status"` // "SUCCESS", "REJECTED", "PENDING"
	Timestamp         time.Time         `json:"timestamp"`
	ProviderMetadata  map[string]string `json:"providerMetadata,omitempty"`
}

// TopUpRequest defines target parameters to initiate an online wallet balance load.
type TopUpRequest struct {
	UserID      uuid.UUID `json:"userId"`
	AmountPKR   int64     `json:"amountPkr"`
	Description string    `json:"description"`
	CallbackURL string    `json:"callbackUrl"`
}

// InitiationResponse contains client redirect information produced by the payment gateway.
type InitiationResponse struct {
	CheckoutURL string            `json:"checkoutUrl"`
	FormFields  map[string]string `json:"formFields"`
	TrackingID  string            `json:"trackingId"`
}

// PaymentGateway defines the structural Adapter pattern target interface (SE-423 §6.3).
// It decouples the internal Wallet ledger service from provider-specific APIs and data formats.
type PaymentGateway interface {
	ProviderName() string
	InitiateTopUp(ctx context.Context, req TopUpRequest) (*InitiationResponse, error)
	VerifyWebhook(ctx context.Context, rawPayload []byte, signature string) (*VerifiedPayment, error)
}

// JazzCashConfig holds integration credentials and secret keys for the JazzCash adapter.
type JazzCashConfig struct {
	MerchantID string
	Password   string
	IntegritySalt string
	GatewayURL string
}

// JazzCashRawCallback represents the proprietary Adaptee payload format sent by JazzCash HTTP webhooks.
type JazzCashRawCallback struct {
	TxnRefNo        string `json:"pp_TxnRefNo"`
	Amount          string `json:"pp_Amount"`       // integer paisas (e.g. "100000" for PKR 1000.00)
	ResponseCode    string `json:"pp_ResponseCode"` // "000" means success
	ResponseMessage string `json:"pp_ResponseMessage"`
	BillReference   string `json:"pp_BillReference"` // embedded internal userId
	TxnDateTime     string `json:"pp_TxnDateTime"`
	SecureHash      string `json:"pp_SecureHash"`
}

// JazzCashAdapter implements PaymentGateway, translating JazzCash proprietary structures to VerifiedPayment.
type JazzCashAdapter struct {
	cfg JazzCashConfig
}

// NewJazzCashAdapter constructs an initialized JazzCash payment adapter.
func NewJazzCashAdapter(cfg JazzCashConfig) *JazzCashAdapter {
	return &JazzCashAdapter{cfg: cfg}
}

func (a *JazzCashAdapter) ProviderName() string {
	return "JazzCash"
}

// InitiateTopUp translates an internal TopUpRequest into a JazzCash formatted post payload.
func (a *JazzCashAdapter) InitiateTopUp(ctx context.Context, req TopUpRequest) (*InitiationResponse, error) {
	if req.AmountPKR <= 0 {
		return nil, errors.New("top-up amount must be strictly positive")
	}

	txnRef := fmt.Sprintf("JC-%d-%s", time.Now().UnixNano(), req.UserID.String()[:8])
	amountPaisas := fmt.Sprintf("%d", req.AmountPKR*100) // 1 PKR = 100 paisas

	fields := map[string]string{
		"pp_MerchantID":    a.cfg.MerchantID,
		"pp_Password":      a.cfg.Password,
		"pp_TxnRefNo":      txnRef,
		"pp_Amount":        amountPaisas,
		"pp_TxnCurrency":   "PKR",
		"pp_BillReference": req.UserID.String(),
		"pp_Description":   req.Description,
		"pp_ReturnURL":     req.CallbackURL,
	}

	// Calculate secure hash for outbound payload
	fields["pp_SecureHash"] = a.computeSecureHash(fields)

	return &InitiationResponse{
		CheckoutURL: a.cfg.GatewayURL,
		FormFields:  fields,
		TrackingID:  txnRef,
	}, nil
}

// VerifyWebhook verifies the integrity hash and adapts the JazzCash webhook payload to VerifiedPayment.
func (a *JazzCashAdapter) VerifyWebhook(ctx context.Context, rawPayload []byte, signature string) (*VerifiedPayment, error) {
	var cb JazzCashRawCallback
	if err := json.Unmarshal(rawPayload, &cb); err != nil {
		return nil, ErrMalformedPayload
	}

	// Verify Secure Hash if secret salt is configured
	if a.cfg.IntegritySalt != "" {
		fields := map[string]string{
			"pp_TxnRefNo":        cb.TxnRefNo,
			"pp_Amount":          cb.Amount,
			"pp_ResponseCode":    cb.ResponseCode,
			"pp_ResponseMessage": cb.ResponseMessage,
			"pp_BillReference":   cb.BillReference,
			"pp_TxnDateTime":     cb.TxnDateTime,
		}
		expectedHash := a.computeSecureHash(fields)
		computedSig := signature
		if computedSig == "" {
			computedSig = cb.SecureHash
		}
		if !strings.EqualFold(expectedHash, computedSig) {
			return nil, ErrInvalidSignature
		}
	}

	// Translate ResponseCode: "000" is successful authorization in JazzCash
	if cb.ResponseCode != "000" {
		return nil, fmt.Errorf("%w: JazzCash code %s (%s)", ErrPaymentRejected, cb.ResponseCode, cb.ResponseMessage)
	}

	// Parse paisas back into integer PKR
	paisas, err := strconv.ParseInt(cb.Amount, 10, 64)
	if err != nil || paisas <= 0 {
		return nil, ErrMalformedPayload
	}
	amountPKR := paisas / 100

	// Extract target user UUID from bill reference
	uid, err := uuid.Parse(cb.BillReference)
	if err != nil {
		return nil, fmt.Errorf("%w: invalid user reference in payment payload", ErrMalformedPayload)
	}

	return &VerifiedPayment{
		ProviderReference: cb.TxnRefNo,
		UserID:            uid,
		AmountPKR:         amountPKR,
		Status:            "SUCCESS",
		Timestamp:         time.Now().UTC(),
		ProviderMetadata: map[string]string{
			"gateway":         a.ProviderName(),
			"responseMessage": cb.ResponseMessage,
			"rawCode":         cb.ResponseCode,
		},
	}, nil
}

// computeSecureHash computes an HMAC-SHA256 string from alphabetically sorted field values.
func (a *JazzCashAdapter) computeSecureHash(fields map[string]string) string {
	var keys []string
	for k := range fields {
		if k != "pp_SecureHash" && fields[k] != "" {
			keys = append(keys, k)
		}
	}
	sort.Strings(keys)

	var b strings.Builder
	b.WriteString(a.cfg.IntegritySalt)
	for _, k := range keys {
		b.WriteString("&")
		b.WriteString(fields[k])
	}

	mac := hmac.New(sha256.New, []byte(a.cfg.IntegritySalt))
	mac.Write([]byte(b.String()))
	return strings.ToUpper(hex.EncodeToString(mac.Sum(nil)))
}

// MockPaymentAdapter is a test double implementation of PaymentGateway for testing without network requests.
type MockPaymentAdapter struct {
	Name string
}

func NewMockPaymentAdapter() *MockPaymentAdapter {
	return &MockPaymentAdapter{Name: "MockGateway"}
}

func (m *MockPaymentAdapter) ProviderName() string {
	return m.Name
}

func (m *MockPaymentAdapter) InitiateTopUp(ctx context.Context, req TopUpRequest) (*InitiationResponse, error) {
	return &InitiationResponse{
		CheckoutURL: "https://mock-gateway.giki.edu.pk/pay",
		TrackingID:  "MOCK-" + uuid.NewString()[:8],
		FormFields:  map[string]string{"amount": strconv.FormatInt(req.AmountPKR, 10)},
	}, nil
}

func (m *MockPaymentAdapter) VerifyWebhook(ctx context.Context, rawPayload []byte, signature string) (*VerifiedPayment, error) {
	if signature == "invalid" {
		return nil, ErrInvalidSignature
	}
	return &VerifiedPayment{
		ProviderReference: "MOCK-REF-12345",
		UserID:            uuid.New(),
		AmountPKR:         1500,
		Status:            "SUCCESS",
		Timestamp:         time.Now().UTC(),
	}, nil
}
