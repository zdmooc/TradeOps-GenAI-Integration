# Trading Policies

## Order Size Limits
- Maximum single order size: 10,000 units for equities
- Maximum single order size: 50 contracts for options
- Maximum notional value per order: $1,000,000

## Pre-Trade Risk Checks
- All orders must pass real-time risk validation before execution
- Duplicate order detection: reject identical orders within 5-second window
- Fat-finger check: reject orders exceeding 10x average daily volume

## Approved Instruments
- US equities listed on NYSE, NASDAQ
- ETFs with daily volume > 100,000 shares
- Paper trading mode: all symbols accepted (no real execution)

## Compliance Rules
- No trading during blackout periods (earnings announcements)
- Wash sale prevention: flag same-symbol BUY after SELL within 30 days
- All trades must have a documented reason/rationale
