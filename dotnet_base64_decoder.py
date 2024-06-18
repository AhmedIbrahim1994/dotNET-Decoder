import os
import sys
import clr
import base64
import logging
from tabulate import tabulate

# Add dnlib reference
dnlib_dll_path = os.path.join(os.path.dirname(__file__), "dnlib")
clr.AddReference(dnlib_dll_path)

# Import dnlib modules
import dnlib
from dnlib.DotNet import ModuleDefMD, MemberRef
from dnlib.DotNet.Emit import OpCodes
from dnlib.DotNet.Writer import ModuleWriterOptions

class Base64StringDecoder:
    """
    Class to decode base64 strings found in a .NET module and modify the module accordingly.
    """

    def __init__(self, file_path):
        """
        Initialize the decoder with the path to the .NET file.

        Args:
            file_path (str): Path to the .NET file to decode.
        """
        self.file_path = file_path
        self.file_module = ModuleDefMD.Load(file_path)
        self.base64_calls = []

    def identify_base64_calls(self):
        """
        Identify method calls to System.Convert.FromBase64String in the .NET module.
        """
        for module_type in self.file_module.Types:
            for method in module_type.Methods:
                if not method.HasBody:
                    continue

                for insn in method.Body.Instructions:
                    if insn.OpCode == OpCodes.Call:
                        operand = insn.Operand
                        if isinstance(operand, MemberRef):
                            if (operand.DeclaringType.FullName == "System.Convert" and
                                operand.Name == "FromBase64String"):
                                prev_insn = method.Body.Instructions[method.Body.Instructions.IndexOf(insn) - 1]
                                if prev_insn.OpCode == OpCodes.Ldstr:
                                    self.base64_calls.append((method, insn, prev_insn))

    def decode_base64_strings(self):
        """
        Decode identified base64 strings and modify the .NET module.
        
        Returns:
            list: List of tuples containing (base64_string, decoded_string).
        """
        decoded_strings = []
        for method, call_insn, str_insn in self.base64_calls:
            base64_str = str_insn.Operand
            try:
                decoded_bytes = base64.b64decode(base64_str)
                decoded_str = decoded_bytes.decode('utf-8')
                decoded_strings.append((base64_str, decoded_str))
                str_insn.Operand = decoded_str
                str_insn.OpCode = OpCodes.Ldstr
                call_insn.OpCode = OpCodes.Nop
            except Exception as e:
                logging.error(f"Failed to decode Base64 string {base64_str}: {e}")
        return decoded_strings

    def save_module(self):
        """
        Save the modified .NET module to a new file.
        
        Returns:
            str: Path to the saved module file.
        """
        options = ModuleWriterOptions(self.file_module)
        options.Logger = dnlib.DotNet.DummyLogger.NoThrowInstance

        split_name = self.file_path.rsplit(".", 1)
        if len(split_name) == 1:
            cleaned_filename = f"{split_name[0]}_decoded.exe"
        else:
            cleaned_filename = f"{split_name[0]}_decoded.{split_name[1]}"

        self.file_module.Write(cleaned_filename, options)
        return cleaned_filename

def main():
    """
    Main function to decode base64 strings in a .NET module.
    """
    if len(sys.argv) < 2:
        sys.exit("[!] Usage: dotnet_base64_decoder.py <dotnet_file_path>")

    file_path = sys.argv[1]

    if not os.path.exists(file_path):
        sys.exit("[-] File not found")

    if not os.path.isabs(file_path):
        file_path = os.path.abspath(file_path)

    decoder = Base64StringDecoder(file_path)
    decoder.identify_base64_calls()

    decoded_strings = decoder.decode_base64_strings()
    if decoded_strings:
        table_headers = ["Encoded Base64", "Decoded Value"]
        print(tabulate(decoded_strings, headers=table_headers, tablefmt="grid"))

        print(f"\nNumber of decoded strings: {len(decoded_strings)}")

        new_file_path = decoder.save_module()
        print(f"Modified binary saved as: {new_file_path}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
