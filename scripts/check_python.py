"""Verifica o interpretador antes de instalar dependencias; somente biblioteca padrao."""
import platform
import struct
import sys
import sysconfig


def main():
    bits = struct.calcsize('P') * 8
    tag = sysconfig.get_platform()
    print(f'Python detectado: {platform.python_implementation()} {platform.python_version()} | {bits} bits | {tag}', flush=True)
    supported = (sys.implementation.name == 'cpython' and sys.version_info[:2] == (3, 12) and bits == 64)
    if sys.platform == 'win32':
        supported = supported and tag == 'win-amd64'
    if not supported:
        print('Este projeto requer CPython 3.12 de 64 bits; no Windows, use a edicao x64 (AMD64).', flush=True)
        print('Feche o servidor, renomeie .venv para uma pasta de backup e crie outra com: py -3.12 -m venv .venv', flush=True)
        print('Nao apague instance/ nem .env: eles guardam seus cadastros e configuracoes.', flush=True)
        print('Consulte a secao de erro do NumPy no README.md.', flush=True)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
