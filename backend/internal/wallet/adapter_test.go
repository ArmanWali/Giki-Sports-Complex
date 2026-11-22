package wallet_test

import (
	"context"
	"encoding/json"
	"testing"

	"github.com/google/uuid"
	"giki-sports-backend/internal/wallet"
)

func TestAdapterPattern_JazzCashInitiation(t *testing.T) {
	cfg := wallet.JazzCashConfig{
		MerchantID:    "TEST_MERCHANT_01",
		Password:      "SecretPass123",
		IntegritySalt: "TEST_SALT_XYZ",
		GatewayURL:    "https://sandbox.jazzcash.com.pk/CustomerPortal/transactionmanagement/merchantform/",
	}
	adapter := wallet.NewJazzCashAdapter(cfg)
	if adapter.ProviderName() != "JazzCash" {
		t.Fatalf("expected ProviderName JazzCash, got %s", adapter.ProviderName())
	}

	testUser := uuid.New()
	req := wallet.TopUpRequest{
		UserID:      testUser,
		AmountPKR:   500, // PKR 500 = 50000 paisas
		Description: "Wallet Balance Load",
		CallbackURL: "https://sports.giki.edu.pk/api/wallet/callback",
	}

	res, err := adapter.InitiateTopUp(context.Background(), req)
	if err != nil {
		t.Fatalf("InitiateTopUp failed: %v", err)
	}

	if res.CheckoutURL != cfg.GatewayURL {
		t.Errorf("expected checkout URL %s, got %s", cfg.GatewayURL, res.CheckoutURL)
	}
	if res.FormFields["pp_Amount"] != "50000" {
		t.Errorf("expected 50000 paisas, got %s", res.FormFields["pp_Amount"])
	}
	if res.FormFields["pp_BillReference"] != testUser.String() {
		t.Errorf("expected bill reference %s, got %s", testUser.String(), res.FormFields["pp_BillReference"])
	}
	if res.FormFields["pp_SecureHash"] == "" {
		t.Errorf("expected computed secure hash, got empty string")
	}
}

func TestAdapterPattern_JazzCashWebhookVerification(t *testing.T) {
	cfg := wallet.JazzCashConfig{
		MerchantID:    "TEST_MERCHANT_01",
		Password:      "SecretPass123",
		IntegritySalt: "", // Disable hash verification for simple payload test
	}
	adapter := wallet.NewJazzCashAdapter(cfg)

	testUser := uuid.New()
	rawCallback := wallet.JazzCashRawCallback{
		TxnRefNo:        "TXN-JAZZ-998822",
		Amount:          "150000", // 1500 PKR
		ResponseCode:    "000",    // Success code
		ResponseMessage: "Transaction Approved",
		BillReference:   testUser.String(),
		TxnDateTime:     "20261122150000",
	}

	payloadBytes, err := json.Marshal(rawCallback)
	if err != nil {
		t.Fatalf("marshal failed: %v", err)
	}

	// 1. Valid success callback
	payment, err := adapter.VerifyWebhook(context.Background(), payloadBytes, "")
	if err != nil {
		t.Fatalf("expected successful webhook verification, got error: %v", err)
	}

	if payment.AmountPKR != 1500 {
		t.Errorf("expected 1500 PKR, got %d", payment.AmountPKR)
	}
	if payment.ProviderReference != "TXN-JAZZ-998822" {
		t.Errorf("expected provider reference TXN-JAZZ-998822, got %s", payment.ProviderReference)
	}
	if payment.UserID != testUser {
		t.Errorf("expected userId %s, got %s", testUser, payment.UserID)
	}
	if payment.Status != "SUCCESS" {
		t.Errorf("expected status SUCCESS, got %s", payment.Status)
	}

	// 2. Rejection response code from provider
	rawCallback.ResponseCode = "124"
	rawCallback.ResponseMessage = "Insufficient Balance in Mobile Account"
	rejBytes, _ := json.Marshal(rawCallback)

	_, err = adapter.VerifyWebhook(context.Background(), rejBytes, "")
	if err == nil {
		t.Fatalf("expected error for non-zero response code, got nil")
	}

	// 3. Malformed JSON payload
	_, err = adapter.VerifyWebhook(context.Background(), []byte("invalid-json"), "")
	if err == nil {
		t.Fatalf("expected malformed payload error, got nil")
	}
}

func TestAdapterPattern_MockPaymentAdapter(t *testing.T) {
	var gateway wallet.PaymentGateway = wallet.NewMockPaymentAdapter()
	if gateway.ProviderName() != "MockGateway" {
		t.Errorf("expected MockGateway, got %s", gateway.ProviderName())
	}

	initRes, err := gateway.InitiateTopUp(context.Background(), wallet.TopUpRequest{AmountPKR: 100})
	if err != nil {
		t.Fatalf("initiate failed: %v", err)
	}
	if initRes.CheckoutURL == "" {
		t.Errorf("expected checkout URL")
	}

	verified, err := gateway.VerifyWebhook(context.Background(), nil, "valid")
	if err != nil {
		t.Fatalf("verify failed: %v", err)
	}
	if verified.AmountPKR != 1500 {
		t.Errorf("expected 1500 PKR, got %d", verified.AmountPKR)
	}
}
