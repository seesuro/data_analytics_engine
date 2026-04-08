def debug_state(stage, state):
    print(f"\n{'='*20} {stage} {'='*20}")
    for k, v in state.items():
        try:
            print(f"{k}: {str(v)[:200]}")
        except:
            print(f"{k}: <unprintable>")