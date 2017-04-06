#!/usr/bin/env python
# coding=utf-8

import math
from random import randint


def generate_id(length):
    return reduce(lambda r, _: r + chr(randint(0, 255)), range(length), "")


def xor(node_one_id, node_two_id):
    result = 0

    length = len(node_one_id)
    for i in range(length):
        result = (result << 8) + (ord(node_one_id[i]) ^ ord(node_two_id[i]))

    return result


def get_routing_table_index(distance):
    if distance == 0:
        return 0
    else:
        return int(math.floor(math.log(math.fabs(distance), 2.0)))
