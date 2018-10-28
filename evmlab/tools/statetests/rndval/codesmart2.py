import random
import evmdasm
import evmcodegen
from evmcodegen.codegen import Rnd
from .code import _RndCodeBase
from .address import RndAddress, RndDestAddress, RndAddressType
from .base import WeightedRandomizer


VALUEMAP ={
    evmdasm.argtypes.Address: lambda: RndDestAddress().as_bytes(),
    evmdasm.argtypes.Word: lambda: Rnd.byte_sequence(32),
    evmdasm.argtypes.Timestamp: lambda: Rnd.byte_sequence(4),
    evmdasm.argtypes.Data: lambda: Rnd.byte_sequence(Rnd.uni_integer(0, Rnd.opcode())),
    evmdasm.argtypes.CallValue: lambda: Rnd.uni_integer(0,1024),
    evmdasm.argtypes.Gas: lambda: Rnd.uni_integer(0,1024),
    evmdasm.argtypes.Length: lambda: Rnd.small_memory_length_1024(),
    evmdasm.argtypes.MemOffset: lambda: Rnd.small_memory_length_1024(),
    evmdasm.argtypes.Index256: lambda: Rnd.uni_integer(1,256),
    evmdasm.argtypes.Index64: lambda: Rnd.uni_integer(1,64),
    evmdasm.argtypes.Index32: lambda: Rnd.length_32(),
    evmdasm.argtypes.Byte: lambda: Rnd.byte_sequence(1),
    evmdasm.argtypes.Bool: lambda: Rnd.byte_sequence(1),
    evmdasm.argtypes.Value: lambda: Rnd.uni_integer(),
    #evmdasm.argtypes.Label: lambda: 0xc0fefefe,  # this is handled by fix_code_layout (fix jumps)
}


class InstructionMutators:

    @staticmethod
    def drop_item(instructions, amount=1):
        len_instr = len(instructions)
        for _ in range(amount):
            index = Rnd.uni_integer(0, len_instr-1 )
            del instructions[index]
        return instructions

    @staticmethod
    def dup_instruction(instructions, amount=1):
        len_instr = len(instructions)
        for _ in range(amount):
            index = Rnd.uni_integer(0, len_instr - 1)
            instructions.insert(index, instructions[index].clone())
        return instructions

    @staticmethod
    def randomize_operand(instructions, amount=1):
        len_instr = len(instructions)
        for _ in range(amount):
            index = Rnd.uni_integer(0, len_instr - 1)
            Rnd.randomize_operand(instructions[index])
        return instructions

    @staticmethod
    def insert_random_instructions(instructions, amount=1):
        len_instr = len(instructions)
        for _ in range(amount):
            index = Rnd.uni_integer(0, len_instr - 1)
            instructions.insert(index, evmdasm.registry.create_instruction(opcode=Rnd.uni_integer(0x00, 0xff)))
            Rnd.randomize_operand(instructions[index])
        return instructions


class BytecodeMutators:

    # add external mutation engines?

    @staticmethod
    def drop_byte(bytecode, amount=1):
        len_instr = len(bytecode)
        for _ in range(amount):
            index = Rnd.uni_integer(0, len_instr - 1)
            bytecode = bytecode[:index] + bytecode[index + 1:]
        return bytecode


    @staticmethod
    def dup_byte(bytecode, amount=1):
        len_instr = len(bytecode)
        for _ in range(amount):
            index = Rnd.uni_integer(0, len_instr - 1)
            bytecode = bytecode[:index] + bytes([bytecode[index], bytecode[index]]) + bytecode[index+1:]
        return bytecode

    @staticmethod
    def insert_random_bytes(bytecode, amount=1):
        len_instr = len(bytecode)
        for _ in range(amount):
            index = Rnd.uni_integer(0, len_instr - 1)
            bytecode = bytecode[:index] + Rnd.byte_sequence(1) + bytecode[index + 1:]
        return bytecode

    @staticmethod
    def switch_random(bytecode, amount=1):
        len_instr = len(bytecode)
        size = Rnd.uni_integer(0, amount)
        from_index = Rnd.uni_integer(0, len_instr - 1)   # bytecode[from_index:index+size]
        to_index = Rnd.uni_integer(0, len_instr - 1)     # bytecode[to_index:index+size]

        first_index=min(from_index, to_index)
        second_index=max(from_index, to_index)

        newcode = [bytecode[:first_index],                      #0
                  bytecode[first_index:first_index+size],       #1  switch
                  bytecode[first_index+size:second_index],      #2
                  bytecode[second_index:second_index+size],     #3  switch
                  bytecode[second_index+size:]]                 #4
        bytecode = newcode[0] + newcode[3] + newcode[2] + newcode[1] + newcode[4]
        return bytecode


class RndCodeSmart2(_RndCodeBase):
    """
    Random bytecode based on stat spread of instructions
    """
    placeholder = "[CODE]"

    # analyzed based on statedump.json

    def generate(self, length=None):
        distribution = evmcodegen.distributions.EVM_CATEGORY  # override this in here to adjust weights
        if length is None:
            length = distribution.avg
        generator = evmcodegen.generators.distribution.GaussDistrCodeGen(distribution=distribution)

        evmcode = evmcodegen.codegen.CodeGen()\
            .generate(generator=generator, length=length, min_gas=self._config_getint("engine.RndCodeSmart2.min_gas", 100))\

        # fix the stack and code in 99.5% of cases
        if Rnd.uni_integer(0,1000) <= self._config_getint("engine.RndCodeSmart2.fixes.fix_stack_arguments.p", 995):
            evmcode.fix_stack_arguments(valuemap=VALUEMAP)\
                .fix_jumps()

        # fix stack balance in 95% of cases
        if Rnd.uni_integer(0,1000) <= self._config_getint("engine.RndCodeSmart2.fixes.fix_stack_balance.p", 950):
            # balance it?
            evmcode.fix_stack_balance()

        ##### store some metrix
        self._addresses_seen = evmcode._addresses_seen

        ######## mutation ########

        # mutate instructions in 1% of cases - likely invalid code
        if Rnd.uni_integer(0,1000) <= self._config_getint("engine.RndCodeSmart2.mutate.instructions.p", 10):
            weights = {InstructionMutators.randomize_operand: self._config_getint("engine.RndCodeSmart2.mutate.instructions.randomize_operand.weight", 60),
                       InstructionMutators.drop_item: self._config_getint("engine.RndCodeSmart2.mutate.instructions.drop_item.weight", 10),
                       InstructionMutators.dup_instruction: self._config_getint("engine.RndCodeSmart2.mutate.instructions.dup_instruction.weight", 20),
                       InstructionMutators.insert_random_instructions: self._config_getint("engine.RndCodeSmart2.mutate.instructions.insert_random_instructions.weight", 10)}
            mutator = WeightedRandomizer(weights=weights)
            evmcode.instructions = mutator.random()(evmcode.instructions,Rnd.uni_integer(1,self._config_getint("engine.RndCodeSmart2.mutate.instructions.max_amount", 3)))

        # mutate evmbytecode in 0.1% of  - very likely invalid code
        if Rnd.uni_integer(0, 1000) <= self._config_getint("engine.RndCodeSmart2.mutate.bytecode.p", 1):
            weights = {BytecodeMutators.dup_byte: self._config_getint("engine.RndCodeSmart2.mutate.bytecode.dup_byte.weight", 50),
                       BytecodeMutators.insert_random_bytes: self._config_getint("engine.RndCodeSmart2.mutate.bytecode.insert_random_bytes.weight", 10),
                       BytecodeMutators.drop_byte: self._config_getint("engine.RndCodeSmart2.mutate.bytecode.drop_byte.weight", 20),
                       BytecodeMutators.switch_random: self._config_getint("engine.RndCodeSmart2.mutate.bytecode.switch_random.weight", 20)}
            mutator = WeightedRandomizer(weights=weights)
            evmcode.instructions = evmdasm.EvmBytecode(mutator.random()(evmcode.assemble().as_bytes, Rnd.uni_integer(1, self._config_getint("engine.RndCodeSmart2.mutate.bytecode.max_amount", 3)))).disassemble()

        return "0x%s" % evmcode.assemble().as_hexstring
