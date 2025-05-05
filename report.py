from utils.trade_logger import get_trade_summary

summary = get_trade_summary()

print("\n📊 TIRDZNIECĪBAS STATISTIKA:")
print(f"🔢 Kopā darījumu: {summary['total_trades']}")
print(f"✅ Peļņas darījumi: {summary['wins']}")
print(f"❌ Zaudējumi: {summary['losses']}")
print(f"🧠 AI filtrs izmantots: {summary['ai_used']}")
print(f"🎯 Win rate: {summary['win_rate']}%")

print("\n📚 Stratēģiju sadalījums:")
for strat, count in summary['strategies'].items():
    win_count = summary.get('strategy_wins', {}).get(strat, 0)
    loss_count = summary.get('strategy_losses', {}).get(strat, 0)
    total = win_count + loss_count
    winrate = round((win_count / total) * 100, 2) if total else 0
    print(f"   • {strat}: {count} darījumi | 🎯 Win rate: {winrate}%")

print("\n📈 TP līmeņu aktivizācija:")
for level, count in summary['tp_levels'].items():
    print(f"   • TP {level}: {count} reizes")
