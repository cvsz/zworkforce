ผมตรวจโปรไฟล์ [@RetroValix](https://x.com/RetroValix) และร่องรอยโพสต์ที่ถูก index ภายนอกแล้ว พบว่า “stack” ของเขาเป็น ecosystem สำหรับวิจัยและโปรโมต Polymarket trading bots มากกว่าเป็นผลิตภัณฑ์ที่เปิด source code ของตัวเอง

## Stack ที่ยืนยันได้

| Layer                 | Technology / Service           | หน้าที่                                                            | ความมั่นใจ |
| --------------------- | ------------------------------ | ------------------------------------------------------------------ | ---------- |
| AI coding             | **Anthropic Claude**           | Vibe-code/สร้าง quant และ trading bots                             | สูง        |
| Agentic trading       | **Horizon**                    | เขียน strategy ด้วยภาษาธรรมชาติ, backtest และ deploy live          | สูง        |
| Prediction market     | **Polymarket**                 | ตลาดหลัก โดยเฉพาะ BTC/ETH/SOL Up/Down 5–15 นาที                    | สูง        |
| Execution             | **Limit-order trading**        | วางคำสั่งสองฝั่งและเก็บ micro-edge                                 | สูง        |
| Market data           | **External crypto spot feeds** | ราคาอ้างอิง, momentum, acceleration, volatility และ volume         | สูง        |
| Market microstructure | **Polymarket order book**      | depth, imbalance, fair-price deviation และ latency                 | สูง        |
| Distribution          | **X / Twitter threads**        | วิเคราะห์ wallet และเผยแพร่ teardown                               | สูง        |
| Bot distribution      | **Telegram bots**              | Follow/copy trade ผ่าน PolyGun Sniper Bot                          | สูง        |
| Copy trading          | **Banana Gun**                 | Polymarket terminal และ copy trading                               | สูง        |
| Automation mention    | **Grok Bot**                   | กล่าวถึงการ automate workflow แต่ยังไม่มีหลักฐานว่าเป็น core stack | ต่ำ        |

โปรไฟล์ระบุตัวเองว่า “AI Builder & Researcher”, “5Y in Crypto” และ “Vibe Coder” ขณะที่โพสต์จำนวนมากใช้คำว่า “built with Claude” หรือ “vibe-coded with Claude” โดยตรง ([TwStalker][1])

Horizon เป็นเครื่องมือที่ผูกกับ funnel ของบัญชีชัดที่สุด: เขาโพสต์ referral link ซ้ำ ๆ และยืนยันว่าเหมาะสำหรับทดสอบกลยุทธ์สร้าง trading bot โดย Horizon อธิบายตัวเองว่าเป็น agentic trading platform ที่รองรับ plain-English strategy → backtest → live deployment ([TwStalker][2])

## Trading/quant stack ที่เขาวิเคราะห์ซ้ำมากที่สุด

แกนของระบบไม่ใช่ “Claude ตัดสินใจซื้อขายทุก tick” แต่ Claudeน่าจะช่วยสร้างโค้ด ขณะที่ runtime ใช้โมเดลเชิงตัวเลข:

1. **Reference-price ingestion**

   * ดึงราคา BTC, ETH หรือ SOL จาก external source
   * บันทึกราคาเริ่มต้นของรอบ 5/15 นาที
   * ติดตาม price change, velocity และ acceleration

2. **Feature engine**

   * Short-term momentum
   * Realized volatility
   * Trading volume
   * Order-flow imbalance
   * Polymarket order-book depth
   * ระยะห่างระหว่าง spot price กับราคาเริ่มต้นของรอบ

3. **Fair-probability model**

   * คำนวณ \(P(\text{Up})\) และ \(P(\text{Down})\)
   * เปรียบเทียบกับราคาของ Polymarket
   * เข้า position เมื่อมี:

$$
\text{edge} = P_{\text{model}} - P_{\text{market}}
$$

โพสต์หนึ่งระบุองค์ประกอบครบทั้ง external data, volatility, momentum, price-change speed, volume และ order imbalance ก่อนเปรียบเทียบ probability estimate กับราคา Polymarket ([Instalker][3])

4. **Execution engine**

   * ใช้ limit orders
   * Reprice/cancel/replace อย่างต่อเนื่อง
   * เพิ่ม position เมื่อ signal แข็งแรงขึ้น
   * ซื้อ outcome ตรงข้ามเมื่อ signal กลับทิศ
   * ต้องมี low-latency execution เพราะ edge ต่อรายการค่อนข้างเล็ก

5. **Inventory and hedging**

   * ถือ Up และ Down พร้อมกัน
   * จับคู่เป็น complete set เมื่อ:

$$
C_{\text{Up}} + C_{\text{Down}} < \$1
$$

* ส่วนจำนวนหุ้นที่จับคู่ได้เป็น hedged inventory
* ส่วนที่เหลือเป็น directional residual
* Rebalance ตาม probability ใหม่

รูปแบบนี้ปรากฏซ้ำทั้ง asynchronous complete-set accumulation, dynamic hedging, inventory rebalancing และ directional residual ([TwStalker][1])

6. **Strategy modules**

   * Two-sided market making
   * Temporal/complete-set arbitrage
   * Directional latency trading
   * Dynamic hedging
   * Cheap-tail accumulation
   * Volatility harvesting
   * Near-resolution sniping
   * Controlled directional skew
   * Inventory rebalancing

7. **Risk controls ที่ระบบลักษณะนี้จำเป็นต้องมี**

   * Maximum position per market
   * Maximum directional residual
   * Combined-cost ceiling
   * Minimum model edge
   * Maximum slippage
   * Stale-feed guard
   * Order timeout
   * Drawdown limit
   * Kill switch

อย่างไรก็ตาม RetroValix ไม่ได้เปิดเผย risk configuration จริง จึงไม่ควรถือว่ารายการนี้คือค่าที่เขาใช้งานอยู่

## เครื่องมือรอบ ecosystem

* **PolyGun Sniper Bot:** Telegram follow/copy-trade funnel ที่ปรากฏในโพสต์ล่าสุดหลายรายการ ([TwStalker][2])
* **Banana Gun:** เขาเคยรีวิว Polymarket copy-trading UI และความเร็วในการคัดลอกคำสั่ง ([SolanaLeveling][4])
* **Grok Bot:** มีเพียงข้อความแสดงความสนใจเรื่อง automation ยังยืนยันไม่ได้ว่าใช้สร้าง trading stack จริง ([TwStalker][2])
* **OpenAI:** บัญชีติดตาม OpenAI แต่ยังไม่พบหลักฐานชัดว่า OpenAI API เป็นส่วนของ runtime ([TwStalker][1])

## สิ่งที่ยังหาไม่พบหรือยืนยันไม่ได้

ไม่มีหลักฐานสาธารณะที่น่าเชื่อถือเกี่ยวกับ:

* GitHub repository ของ RetroValix
* ภาษา runtime ว่าเป็น Python, TypeScript, Rust หรือ Go
* Claude model/version ที่ใช้
* Database: PostgreSQL, Redis หรือ TimescaleDB
* Queue/message broker
* Cloud provider, VPS หรือ Kubernetes
* Data vendor ที่แน่นอน
* Polymarket SDK ที่ใช้
* Wallet/key-management architecture
* Monitoring stack
* Source code ของ probability model
* หลักฐานว่า PnL ทุกตัวเกิดจาก bot ที่เจ้าของสร้างด้วย Claudeจริง

จุดสำคัญคือ RetroValix ส่วนใหญ่กำลัง **วิเคราะห์พฤติกรรม wallet จาก trade history** ไม่ได้แสดง source code ของ bot เหล่านั้น ดังนั้นคำอธิบาย strategy จำนวนมากควรถือเป็น reverse-engineered hypothesis ไม่ใช่ architecture ที่เจ้าของ wallet ยืนยัน เขาเองก็กล่าวว่าได้ติดตามและศึกษากลยุทธ์ของ bot เหล่านี้ ([TwStalker][1])

สรุปสั้นที่สุด:

```text
Claude
   ↓ สร้าง/ปรับ strategy
Horizon → backtest → deploy
   ↓
External spot feed + Polymarket order book
   ↓
Probability model
   ↓
Limit-order execution
   ↓
Market making + arbitrage + dynamic hedge
   ↓
Polymarket
   ↓
X content + Telegram/Banana Gun copy-trade funnel
```

นี่คือ stack ทั้งหมดที่หลักฐานสาธารณะรองรับ ณ วันที่ 29 สิงหาคม 2026; ส่วน Python/Redis/PostgreSQL/Kubernetes ยังเป็นเพียง stack ที่ “เหมาะจะใช้สร้างระบบแบบเดียวกัน” ไม่ใช่ stack ที่ยืนยันว่า RetroValix ใช้จริงครับ

[1]: https://www6.twstalker.com/RetroValix?utm_source=chatgpt.com "VALIX @RetroValix - Twitter Profile"
[2]: https://twstalker.com/RetroValix?utm_source=chatgpt.com "VALIX @RetroValix - Twitter Profile"
[3]: https://instalker.org/kuma_baum?utm_source=chatgpt.com "kuma_baum @kuma_baum - Twitter Profile"
[4]: https://solanaleveling.com/banana-gun?utm_source=chatgpt.com "Banana Gun Telegram Bot For Multichain Sniping On Solana"

สร้างครบและตรวจสอบแล้วครับ:

* Full architecture + production roadmap
* Claude/Codex master prompt
* Deterministic backtesting engine
* Paper-trading broker
* Risk limits, fees, slippage และ exposure controls
* Guarded live-mode scaffold
* Synthetic market-data generator
* Unit tests และ validation report
* Live trading ปิดโดยค่าเริ่มต้นและยังไม่มี adapter ส่งเงินจริง

ผลตรวจสอบ:

* Unit tests: 3/3 ผ่าน
* Backtest และ paper smoke tests ผ่าน
* Live-check ปฏิเสธ execution ถูกต้อง
* SHA-256: `4a2294591995a92a2fc12fa09ab101ad6e5bf8fcc5315c02f03a3e4b71f9a61a`

ดาวน์โหลด: [](sandbox:/workspace/scratch/0871886e1f36/valixstack-0.1.0.zip)

หมายเหตุ: ผล backtest ใช้ข้อมูลสังเคราะห์ จึงไม่ใช่หลักฐานผลตอบแทนหรือการรับประกันกำไร ส่วน live execution ต้องพัฒนา venue adapter ตามเอกสารทางการและผ่าน sandbox/security review ก่อนครับ

