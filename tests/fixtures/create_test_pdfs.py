"""
Script to generate simple test PDF files for testing.

This script creates basic PDF files with text content for use in tests.
Requires reportlab: pip install reportlab
"""

from pathlib import Path

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
except ImportError:
    print("reportlab not installed. Run: pip install reportlab")
    exit(1)


def create_simple_pdf(filepath: str, text_content: str):
    """Create a simple PDF with text content."""
    c = canvas.Canvas(filepath, pagesize=A4)
    width, height = A4

    # Add text at different positions
    c.setFont("Helvetica", 12)
    y_position = height - 50

    for line in text_content.split("\n"):
        if line.strip():
            c.drawString(50, y_position, line)
            y_position -= 20

    c.save()


def create_carteira_oab_sample():
    """Create a sample OAB card PDF."""
    content = """
ORDEM DOS ADVOGADOS DO BRASIL
CARTEIRA DE IDENTIDADE PROFISSIONAL

Nome: JOÃO DA SILVA
Inscrição: 123456
Seccional: OAB/SP
Categoria: ADVOGADO
CPF: 123.456.789-00
Data de Inscrição: 01/01/2020

Situação: ATIVO
    """.strip()

    fixtures_dir = Path(__file__).parent
    filepath = fixtures_dir / "sample_oab.pdf"
    create_simple_pdf(str(filepath), content)
    print(f"Created: {filepath}")


def create_simple_document_sample():
    """Create a simple generic document PDF."""
    content = """
DOCUMENTO DE TESTE

Campo 1: Valor do Campo 1
Campo 2: Valor do Campo 2
Campo 3: Valor do Campo 3

Data: 01/01/2024
Status: Aprovado
    """.strip()

    fixtures_dir = Path(__file__).parent
    filepath = fixtures_dir / "simple_document.pdf"
    create_simple_pdf(str(filepath), content)
    print(f"Created: {filepath}")


def create_multifield_sample():
    """Create a document with multiple fields for testing."""
    content = """
CADASTRO PROFISSIONAL

Nome Completo: MARIA SANTOS OLIVEIRA
CPF: 987.654.321-00
RG: 12.345.678-9
Data de Nascimento: 15/03/1990

Endereço: Rua das Flores, 123
Cidade: São Paulo
Estado: SP
CEP: 01234-567

Telefone: (11) 98765-4321
Email: maria.santos@example.com

Profissão: Engenheira Civil
Registro Profissional: CREA-SP 123456

Status: ATIVO
Data de Cadastro: 10/01/2024
    """.strip()

    fixtures_dir = Path(__file__).parent
    filepath = fixtures_dir / "multifield_document.pdf"
    create_simple_pdf(str(filepath), content)
    print(f"Created: {filepath}")


def create_empty_pdf():
    """Create an empty PDF (no text)."""
    fixtures_dir = Path(__file__).parent
    filepath = fixtures_dir / "empty_document.pdf"

    c = canvas.Canvas(str(filepath), pagesize=A4)
    # Don't add any text
    c.save()
    print(f"Created: {filepath}")


if __name__ == "__main__":
    # Create fixtures directory if it doesn't exist
    fixtures_dir = Path(__file__).parent
    fixtures_dir.mkdir(exist_ok=True)

    print("Creating test PDF fixtures...")
    create_carteira_oab_sample()
    create_simple_document_sample()
    create_multifield_sample()
    create_empty_pdf()
    print("\nAll test PDFs created successfully!")
