#! /usr/bin/env python
# -*- coding: utf-8 -*-
# Author : <github.com/tintinweb>
#
#
# https://github.com/ethereum/testeth/blob/ee0c6776c01b09045a379220c7e490000dae9377/test/tools/fuzzTesting/createRandomTest.cpp
#
from .address import RndAddress, RndAddressType, RndDestAddress, RndByteSequence
from .bytes import RndByteSequence, Rnd0xHash32, RndHash20, RndHash32, RndV
from .hexint import RndHex32, RndBlockGasLimit, RndGasPrice, RndTransactionGasLimit, RndHexInt
from .rlp import RndRlp
from .seed import RandomSeed
from .base import _RndBase, hex2

from .code import RndCodeBytes

import logging

try:
    from .codesmart import RndCodeInstr
    RndCode = RndCodeInstr
except ImportError as ie:
    RndCode = RndCodeBytes
    logging.warning("[!! Exception] Failed to Import RndCodeInstr() - %r"%ie)
    logging.warning("----> Falling back to Random Code Generation based on byte distribution!")
