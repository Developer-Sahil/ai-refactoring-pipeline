// payment.go — Payment processing — cAST Go example.
package payment

import (
	"errors"
	"fmt"
	"time"
)

// PaymentStatus represents the state of a payment transaction.
type PaymentStatus struct {
	ID        string
	Amount    float64
	Currency  string
	Status    string
	CreatedAt time.Time
}

// Processor defines the interface for payment backends.
type Processor interface {
	Charge(amount float64, currency, token string) (string, error)
	Refund(transactionID string, amount float64) error
}

// PaymentService orchestrates charge and refund flows.
type PaymentService struct {
	processor Processor
	logger    Logger
}

// NewPaymentService constructs a PaymentService.
func NewPaymentService(proc Processor, log Logger) *PaymentService {
	return &PaymentService{processor: proc, logger: log}
}

// Charge creates a new payment for the given amount.
func (s *PaymentService) Charge(amount float64, currency, token string) (*PaymentStatus, error) {
	if amount <= 0 {
		return nil, errors.New("amount must be positive")
	}
	txID, err := s.processor.Charge(amount, currency, token)
	if err != nil {
		s.logger.Errorf("charge failed: %v", err)
		return nil, fmt.Errorf("payment failed: %w", err)
	}
	return &PaymentStatus{
		ID:        txID,
		Amount:    amount,
		Currency:  currency,
		Status:    "succeeded",
		CreatedAt: time.Now(),
	}, nil
}

// Refund reverses a previous transaction.
func (s *PaymentService) Refund(txID string, amount float64) error {
	if txID == "" {
		return errors.New("transaction ID is required")
	}
	return s.processor.Refund(txID, amount)
}

// FormatAmount returns a human-readable amount string.
func FormatAmount(amount float64, currency string) string {
	return fmt.Sprintf("%.2f %s", amount, currency)
}
