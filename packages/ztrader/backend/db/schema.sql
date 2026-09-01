-- apps/ztrader/backend/db/schema.sql

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    role VARCHAR(50) NOT NULL DEFAULT 'user', -- admin, operator, user
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS rental_contracts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    start_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    end_date TIMESTAMP WITH TIME ZONE NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS exchange_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    exchange VARCHAR(100) NOT NULL, -- e.g. binance, kucoin
    encrypted_key TEXT NOT NULL,
    encrypted_secret TEXT NOT NULL,
    passphrase TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(50) NOT NULL,
    side VARCHAR(20) NOT NULL, -- buy, sell
    execution_mode VARCHAR(20) NOT NULL, -- paper, live
    notional DOUBLE PRECISION NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    base_amount DOUBLE PRECISION NOT NULL,
    fee DOUBLE PRECISION NOT NULL,
    status VARCHAR(50) NOT NULL, -- open, filled, canceled
    strategy_id VARCHAR(100) NOT NULL,
    request_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(100) NOT NULL, -- risk_denied, strategy_intent, order_filled
    actor VARCHAR(255) NOT NULL, -- strategy_id or user_id
    severity VARCHAR(20) NOT NULL, -- info, warning, critical
    message TEXT NOT NULL,
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tradingview_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker VARCHAR(50) NOT NULL,
    exchange VARCHAR(100) NOT NULL DEFAULT 'binance.com',
    action VARCHAR(20) NOT NULL, -- BUY, SELL, CLOSE
    price DOUBLE PRECISION,
    strategy VARCHAR(100),
    interval VARCHAR(20),
    volume DOUBLE PRECISION,
    message TEXT,
    raw_payload TEXT,
    received_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    processed BOOLEAN NOT NULL DEFAULT FALSE
);
