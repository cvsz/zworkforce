export interface StrategyConfig { name: string; params?: Record<string, any> }

export class ExampleStrategy {
  name: string
  params: Record<string, any>

  constructor(config: StrategyConfig) {
    this.name = config.name
    this.params = config.params ?? {}
  }

  onTick(tick: { price: number }) {
    console.log(`${this.name} tick: ${tick.price}`)
  }

  generateSignals() {
    return [{ signal: 'hold', strategy: this.name }]
  }
}
