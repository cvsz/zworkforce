BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
      FROM pg_constraint
     WHERE conname = 'billing_invoice_intents_supported_currency_check'
       AND conrelid = to_regclass('billing_invoice_intents')
  ) THEN
    ALTER TABLE billing_invoice_intents
      ADD CONSTRAINT billing_invoice_intents_supported_currency_check
      CHECK (currency IN ('THB', 'USD')) NOT VALID;
  END IF;
END
$$;

-- Validation fails closed if pre-existing invoice intents use an unsupported code.
ALTER TABLE billing_invoice_intents
  VALIDATE CONSTRAINT billing_invoice_intents_supported_currency_check;

INSERT INTO billing_schema_migrations (version)
VALUES (2)
ON CONFLICT (version) DO NOTHING;

COMMIT;
