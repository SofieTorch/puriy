import argparse

def main() -> int:
    parser = argparse.ArgumentParser(prog="geodata")
    parser.add_argument("--simplify", type=float, help="Tolerance value")
    parser.add_argument("input", nargs="?")
    args = parser.parse_args()

    print(f"input={args.input}, simplify={args.simplify}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())