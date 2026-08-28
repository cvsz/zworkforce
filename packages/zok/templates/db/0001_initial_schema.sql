-- Zok Conversational Commerce Platform - Initial DB Schema
-- Database: PostgreSQL v15+

BEGIN;

-- 1. Channels (WhatsApp, LINE OA, Messenger, Shopify integration sync statuses)
CREATE TABLE IF NOT EXISTS channels (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    status VARCHAR(20) DEFAULT 'disconnected',
    config JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Customer Profiles
CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    avatar VARCHAR(10),
    phone VARCHAR(30),
    email VARCHAR(100),
    tags TEXT[] DEFAULT '{}',
    assigned_agent VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Conversations (Linking channel, customer, and agent status)
CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    customer_id INT REFERENCES customers(id) ON DELETE CASCADE,
    channel_id VARCHAR(50) REFERENCES channels(id),
    unread_count INT DEFAULT 0,
    last_message_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. Messages (Store conversations threads history logs)
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    conversation_id INT REFERENCES conversations(id) ON DELETE CASCADE,
    sender VARCHAR(20) NOT NULL CHECK (sender IN ('customer', 'agent', 'system')),
    text TEXT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 5. Shopify Orders Cache
CREATE TABLE IF NOT EXISTS shopify_orders (
    id VARCHAR(50) PRIMARY KEY,
    customer_id INT REFERENCES customers(id) ON DELETE CASCADE,
    order_date DATE NOT NULL,
    total_amount NUMERIC(10,2) NOT NULL,
    status VARCHAR(30) NOT NULL
);

-- Create indexing rules for optimization
CREATE INDEX IF NOT EXISTS idx_conversations_last_message_at ON conversations(last_message_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_shopify_orders_customer_id ON shopify_orders(customer_id);

COMMIT;
