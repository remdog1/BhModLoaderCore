def CompareBytes(b1: bytes, b2: bytes):
    min_len = min([len(b1), len(b2)])
    max_len = max([len(b1), len(b2)])

    num_different_bytes = 0

    for nchar in range(min_len):
        if b1[nchar] != b2[nchar]:
            num_different_bytes += 1

    num_different_bytes += max_len - min_len

    return 100 - round(100*num_different_bytes/max_len, 2)


def PrintCompareBytes(b1: bytes, b2: bytes):
    b1 = b1.hex()
    b2 = b2.hex()

    print(b1)
    print(b2)

    for nchar in range(min([len(b1), len(b2)])):
        if b1[nchar] != b2[nchar]:
            print("|", end="")
        else:
            print(" ", end="")

    print()
