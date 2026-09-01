"""SQLAlchemy models for Auto Bot Trader Pro i18n."""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ztrader.abt.utils.database import Base


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String, unique=True)
    googleId: Mapped[Optional[str]] = mapped_column(String, unique=True)
    oauthProvider: Mapped[Optional[str]] = mapped_column(String)
    profilePicture: Mapped[Optional[str]] = mapped_column(String)
    createdAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    exchangeKeys: Mapped[list["ExchangeKey"]] = relationship(back_populates="owner")
    botRuns: Mapped[list["BotRun"]] = relationship(back_populates="user")
    tradeLogs: Mapped[list["TradeLog"]] = relationship(back_populates="user")
    rentalContracts: Mapped[list["RentalContract"]] = relationship(back_populates="user")
    telegramLink: Mapped[Optional["TelegramLink"]] = relationship(back_populates="user", uselist=False)
    promptpayTopups: Mapped[list["PromptPayTopup"]] = relationship(back_populates="user")
    modules: Mapped[list["ModuleRegistration"]] = relationship(back_populates="user")
    notificationPreference: Mapped[Optional["NotificationPreference"]] = relationship(back_populates="user", uselist=False)
    userPreference: Mapped[Optional["UserPreference"]] = relationship(back_populates="user", uselist=False)
    wallet: Mapped[Optional["Wallet"]] = relationship(back_populates="user", uselist=False)
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="user")
    userPlugins: Mapped[list["UserPlugin"]] = relationship(back_populates="user")
    accounts: Mapped[list["Account"]] = relationship(back_populates="user")
    backtestRuns: Mapped[list["BacktestRun"]] = relationship(back_populates="user")
    paperTradingSessions: Mapped[list["PaperTradingSession"]] = relationship(back_populates="user")
    auditLogs: Mapped[list["AuditLog"]] = relationship(back_populates="user")
    secretRotations: Mapped[list["SecretRotation"]] = relationship(back_populates="user")
    mlSignalScores: Mapped[list["MLSignalScore"]] = relationship(back_populates="user")
    strategyOptimizations: Mapped[list["StrategyOptimization"]] = relationship(back_populates="user")


class ExchangeKey(Base):
    __tablename__ = "exchangekey"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exchange: Mapped[str] = mapped_column(String)
    encrypted_key: Mapped[str] = mapped_column(String)
    iv_key: Mapped[str] = mapped_column(String)
    encrypted_secret: Mapped[str] = mapped_column(String)
    iv_secret: Mapped[str] = mapped_column(String)
    createdAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    ownerId: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("user.id"))

    owner: Mapped[Optional["User"]] = relationship(back_populates="exchangeKeys")
    accounts: Mapped[list["Account"]] = relationship(back_populates="exchangeKey")


class Strategy(Base):
    __tablename__ = "strategy"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    description: Mapped[Optional[str]] = mapped_column(String)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    createdAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class BotRun(Base):
    __tablename__ = "botrun"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    userId: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"))
    strategy: Mapped[str] = mapped_column(String)
    symbol: Mapped[str] = mapped_column(String)
    timeframe: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="RUNNING")
    startedAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    stoppedAt: Mapped[Optional[datetime]] = mapped_column(DateTime)

    user: Mapped["User"] = relationship(back_populates="botRuns")
    tradeLogs: Mapped[list["TradeLog"]] = relationship(back_populates="botRun")


class TradeLog(Base):
    __tablename__ = "tradelog"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    botRunId: Mapped[int] = mapped_column(Integer, ForeignKey("botrun.id"))
    side: Mapped[str] = mapped_column(String)
    quantity: Mapped[float] = mapped_column(Float)
    price: Mapped[float] = mapped_column(Float)
    pnl: Mapped[float] = mapped_column(Float, default=0)
    createdAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    userId: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("user.id"))

    botRun: Mapped["BotRun"] = relationship(back_populates="tradeLogs")
    user: Mapped[Optional["User"]] = relationship(back_populates="tradeLogs")


class RentalContract(Base):
    __tablename__ = "rentalcontract"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    userId: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"))
    plan: Mapped[str] = mapped_column(String)
    expiry: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String, default="ACTIVE")
    gracePeriodDays: Mapped[int] = mapped_column(Integer, default=3)
    autoRenew: Mapped[bool] = mapped_column(Boolean, default=False)
    features: Mapped[Optional[str]] = mapped_column(Text)
    createdAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    renewedAt: Mapped[Optional[datetime]] = mapped_column(DateTime)

    user: Mapped["User"] = relationship(back_populates="rentalContracts")


class PromptPayTopup(Base):
    __tablename__ = "promptpaytopup"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    userId: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"))
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String, default="THB")
    status: Mapped[str] = mapped_column(String, default="PENDING")
    createdAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    confirmedAt: Mapped[Optional[datetime]] = mapped_column(DateTime)

    user: Mapped["User"] = relationship(back_populates="promptpayTopups")


class ModuleRegistration(Base):
    __tablename__ = "moduleregistration"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    userId: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"))
    moduleName: Mapped[str] = mapped_column(String)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    createdAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="modules")


class TelegramLink(Base):
    __tablename__ = "telegramlink"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    userId: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), unique=True)
    chatId: Mapped[str] = mapped_column(String)
    username: Mapped[Optional[str]] = mapped_column(String)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    createdAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updatedAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="telegramLink")


class NotificationPreference(Base):
    __tablename__ = "notificationpreference"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    userId: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), unique=True)
    tradeAlerts: Mapped[bool] = mapped_column(Boolean, default=True)
    riskAlerts: Mapped[bool] = mapped_column(Boolean, default=True)
    systemAlerts: Mapped[bool] = mapped_column(Boolean, default=True)
    dailySummary: Mapped[bool] = mapped_column(Boolean, default=True)
    createdAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updatedAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="notificationPreference")


class UserPreference(Base):
    __tablename__ = "userpreference"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    userId: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), unique=True)
    theme: Mapped[str] = mapped_column(String, default="auto")
    language: Mapped[str] = mapped_column(String, default="th")
    primaryColor: Mapped[Optional[str]] = mapped_column(String)
    secondaryColor: Mapped[Optional[str]] = mapped_column(String)
    accentColor: Mapped[Optional[str]] = mapped_column(String)
    dashboardLayout: Mapped[str] = mapped_column(String, default="grid")
    refreshInterval: Mapped[int] = mapped_column(Integer, default=30)
    createdAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updatedAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="userPreference")


class Wallet(Base):
    __tablename__ = "wallet"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    userId: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), unique=True)
    balance: Mapped[float] = mapped_column(Float, default=0)
    currency: Mapped[str] = mapped_column(String, default="THB")
    createdAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updatedAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="wallet")


class Transaction(Base):
    __tablename__ = "transaction"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    userId: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"))
    type: Mapped[str] = mapped_column(String)
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String, default="THB")
    status: Mapped[str] = mapped_column(String, default="PENDING")
    paymentMethod: Mapped[Optional[str]] = mapped_column(String)
    referenceId: Mapped[Optional[str]] = mapped_column(String, unique=True)
    metadataJson: Mapped[Optional[str]] = mapped_column("metadata", Text)
    createdAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completedAt: Mapped[Optional[datetime]] = mapped_column(DateTime)

    user: Mapped["User"] = relationship(back_populates="transactions")


class Plugin(Base):
    __tablename__ = "plugin"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    version: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(String)
    entryPoint: Mapped[str] = mapped_column(String)
    author: Mapped[Optional[str]] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(String)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    createdAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updatedAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    userPlugins: Mapped[list["UserPlugin"]] = relationship(back_populates="plugin")


class UserPlugin(Base):
    __tablename__ = "userplugin"
    __table_args__ = (UniqueConstraint("userId", "pluginId"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    userId: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"))
    pluginId: Mapped[int] = mapped_column(Integer, ForeignKey("plugin.id"))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    config: Mapped[Optional[str]] = mapped_column(Text)
    createdAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="userPlugins")
    plugin: Mapped["Plugin"] = relationship(back_populates="userPlugins")


class Account(Base):
    __tablename__ = "account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    userId: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"))
    exchangeKeyId: Mapped[int] = mapped_column(Integer, ForeignKey("exchangekey.id"))
    label: Mapped[str] = mapped_column(String)
    group: Mapped[Optional[str]] = mapped_column(String)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    createdAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="accounts")
    exchangeKey: Mapped["ExchangeKey"] = relationship(back_populates="accounts")
    positions: Mapped[list["Position"]] = relationship(back_populates="account")


class Position(Base):
    __tablename__ = "position"
    __table_args__ = (UniqueConstraint("accountId", "symbol"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    accountId: Mapped[int] = mapped_column(Integer, ForeignKey("account.id"))
    symbol: Mapped[str] = mapped_column(String)
    side: Mapped[str] = mapped_column(String)
    quantity: Mapped[float] = mapped_column(Float)
    entryPrice: Mapped[float] = mapped_column(Float)
    currentPrice: Mapped[Optional[float]] = mapped_column(Float)
    pnl: Mapped[float] = mapped_column(Float, default=0)
    updatedAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    account: Mapped["Account"] = relationship(back_populates="positions")


class BacktestRun(Base):
    __tablename__ = "backtestrun"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    userId: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"))
    strategyName: Mapped[str] = mapped_column(String)
    symbol: Mapped[str] = mapped_column(String)
    timeframe: Mapped[str] = mapped_column(String)
    startDate: Mapped[datetime] = mapped_column(DateTime)
    endDate: Mapped[datetime] = mapped_column(DateTime)
    initialCapital: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String, default="PENDING")
    results: Mapped[Optional[str]] = mapped_column(Text)
    createdAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completedAt: Mapped[Optional[datetime]] = mapped_column(DateTime)

    user: Mapped["User"] = relationship(back_populates="backtestRuns")


class PaperTradingSession(Base):
    __tablename__ = "papertradingsession"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    userId: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"))
    strategyName: Mapped[str] = mapped_column(String)
    symbol: Mapped[str] = mapped_column(String)
    timeframe: Mapped[str] = mapped_column(String)
    virtualBalance: Mapped[float] = mapped_column(Float, default=10000)
    currentBalance: Mapped[Optional[float]] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String, default="ACTIVE")
    startedAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    stoppedAt: Mapped[Optional[datetime]] = mapped_column(DateTime)

    user: Mapped["User"] = relationship(back_populates="paperTradingSessions")


class AuditLog(Base):
    __tablename__ = "auditlog"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    userId: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("user.id"))
    action: Mapped[str] = mapped_column(String)
    resource: Mapped[str] = mapped_column(String)
    method: Mapped[str] = mapped_column(String)
    statusCode: Mapped[int] = mapped_column(Integer)
    ipAddress: Mapped[Optional[str]] = mapped_column(String)
    userAgent: Mapped[Optional[str]] = mapped_column(String)
    requestData: Mapped[Optional[str]] = mapped_column(Text)
    metadataJson: Mapped[Optional[str]] = mapped_column("metadata", Text)
    createdAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped[Optional["User"]] = relationship(back_populates="auditLogs")


class SecretRotation(Base):
    __tablename__ = "secretrotation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    secretType: Mapped[str] = mapped_column(String)
    secretName: Mapped[str] = mapped_column(String)
    rotatedAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    rotatedBy: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("user.id"))
    previousHash: Mapped[Optional[str]] = mapped_column(String)
    nextRotation: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String, default="ACTIVE")
    metadataJson: Mapped[Optional[str]] = mapped_column("metadata", Text)

    user: Mapped[Optional["User"]] = relationship(back_populates="secretRotations")


class MLSignalScore(Base):
    __tablename__ = "mlsignalscore"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    userId: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"))
    symbol: Mapped[str] = mapped_column(String)
    timeframe: Mapped[str] = mapped_column(String)
    strategy: Mapped[str] = mapped_column(String)
    score: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    features: Mapped[str] = mapped_column(Text)
    prediction: Mapped[Optional[str]] = mapped_column(String)
    executed: Mapped[bool] = mapped_column(Boolean, default=False)
    outcome: Mapped[Optional[str]] = mapped_column(String)
    createdAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="mlSignalScores")


class MLModelTraining(Base):
    __tablename__ = "mlmodeltraining"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    modelType: Mapped[str] = mapped_column(String)
    modelVersion: Mapped[str] = mapped_column(String)
    trainingData: Mapped[str] = mapped_column(Text)
    hyperparameters: Mapped[str] = mapped_column(Text)
    performance: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String)
    startedAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completedAt: Mapped[Optional[datetime]] = mapped_column(DateTime)
    errorMessage: Mapped[Optional[str]] = mapped_column(String)


class StrategyOptimization(Base):
    __tablename__ = "strategyoptimization"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    userId: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"))
    strategy: Mapped[str] = mapped_column(String)
    originalParams: Mapped[str] = mapped_column(Text)
    optimizedParams: Mapped[str] = mapped_column(Text)
    performance: Mapped[str] = mapped_column(Text)
    method: Mapped[str] = mapped_column(String)
    iterations: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="PENDING")
    createdAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completedAt: Mapped[Optional[datetime]] = mapped_column(DateTime)

    user: Mapped["User"] = relationship(back_populates="strategyOptimizations")


class VolatilityPrediction(Base):
    __tablename__ = "volatilityprediction"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String)
    timeframe: Mapped[str] = mapped_column(String)
    predicted: Mapped[float] = mapped_column(Float)
    actual: Mapped[Optional[float]] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    features: Mapped[str] = mapped_column(Text)
    horizon: Mapped[int] = mapped_column(Integer)
    createdAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class TradingViewAlert(Base):
    __tablename__ = "tradingviewalert"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String)
    exchange: Mapped[str] = mapped_column(String, default="binance")
    action: Mapped[str] = mapped_column(String)
    price: Mapped[Optional[float]] = mapped_column(Float)
    strategy: Mapped[Optional[str]] = mapped_column(String)
    interval: Mapped[Optional[str]] = mapped_column(String)
    volume: Mapped[Optional[float]] = mapped_column(Float)
    message: Mapped[Optional[str]] = mapped_column(String)
    rawPayload: Mapped[Optional[str]] = mapped_column(Text)
    receivedAt: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
