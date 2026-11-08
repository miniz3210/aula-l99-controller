from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

DUMP_FILE = (
    PROJECT_ROOT
    / "isp_memory_dumps"
    / "L99_ISP_idle.dmp"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "isp_memory_dumps"
    / "analysis"
    / "cortex_candidates.txt"
)


def valid_stack_pointer(value):
    return (
        0x20000000
        <= value
        <= 0x200FFFFF
    )


def valid_code_pointer(value):
    if value == 0:
        return True

    if not value & 1:
        return False

    address = value & ~1

    return (
        0x00000000
        <= address
        <= 0x001FFFFF
        or
        0x08000000
        <= address
        <= 0x08FFFFFF
        or
        0x10000000
        <= address
        <= 0x10FFFFFF
    )


def score_vector_table(data, offset):
    entries = []
    score = 0

    for index in range(16):
        start = offset + index * 4

        value = int.from_bytes(
            data[start:start + 4],
            byteorder="little",
        )

        entries.append(value)

        if index == 0:
            if valid_stack_pointer(value):
                score += 10
        elif valid_code_pointer(value):
            score += 2

    return score, entries


def main():
    if not DUMP_FILE.exists():
        raise FileNotFoundError(
            f"Dump file not found: {DUMP_FILE}"
        )

    data = DUMP_FILE.read_bytes()

    print(f"Dump: {DUMP_FILE}")
    print(f"Dump bytes: {len(data)}")
    print("Scanning for Cortex vector tables...")

    candidates = []

    for offset in range(
        0,
        len(data) - 64,
        4,
    ):
        stack_pointer = int.from_bytes(
            data[offset:offset + 4],
            "little",
        )

        reset_vector = int.from_bytes(
            data[offset + 4:offset + 8],
            "little",
        )

        if not valid_stack_pointer(
            stack_pointer
        ):
            continue

        if not valid_code_pointer(
            reset_vector
        ):
            continue

        if reset_vector == 0:
            continue

        score, entries = score_vector_table(
            data,
            offset,
        )

        if score < 22:
            continue

        candidates.append(
            {
                "offset": offset,
                "stack": stack_pointer,
                "reset": reset_vector,
                "score": score,
                "entries": entries,
            }
        )

    candidates.sort(
        key=lambda item: (
            -item["score"],
            item["offset"],
        )
    )

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_FILE.open(
        "w",
        encoding="ascii",
    ) as output:
        for index, item in enumerate(
            candidates
        ):
            vectors = ",".join(
                f"0x{value:08X}"
                for value in item["entries"]
            )

            output.write(
                f"index={index}|"
                f"dump_offset=0x"
                f"{item['offset']:08X}|"
                f"stack=0x"
                f"{item['stack']:08X}|"
                f"reset=0x"
                f"{item['reset']:08X}|"
                f"score={item['score']}|"
                f"vectors={vectors}\n"
            )

    print(
        f"Cortex candidates: "
        f"{len(candidates)}"
    )
    print(f"Output: {OUTPUT_FILE}")

    for index, item in enumerate(
        candidates[:20]
    ):
        print(
            f"{index:2d}: "
            f"offset=0x{item['offset']:08X}, "
            f"stack=0x{item['stack']:08X}, "
            f"reset=0x{item['reset']:08X}, "
            f"score={item['score']}"
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        raise SystemExit(
            f"ERROR: {exc}"
        ) from exc