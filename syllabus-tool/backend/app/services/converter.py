import subprocess
import os
import tempfile

def convert_to_pdf(input_bytes: bytes, original_filename: str) -> bytes:
    """
    Converts a document (docx, etc.) to PDF using LibreOffice.
    Returns the PDF bytes.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        # Save input file
        input_path = os.path.join(temp_dir, original_filename)
        with open(input_path, "wb") as f:
            f.write(input_bytes)
        
        # Run LibreOffice conversion
        # libreoffice --headless --convert-to pdf <file> --outdir <dir>
        try:
            # Use a temporary user installation directory to avoid permission issues
            user_install_dir = os.path.join(temp_dir, "user_install")
            
            # Use --unsafe-args to avoid issues with filenames? No, just standard args.
            # Ensure libreoffice is in path.
            subprocess.run(
                [
                    "libreoffice", 
                    "--headless", 
                    "--convert-to", "pdf", 
                    "--outdir", temp_dir,
                    f"-env:UserInstallation=file://{user_install_dir}",
                    input_path
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        except subprocess.CalledProcessError as e:
            print(f"Conversion failed: {e.stderr.decode()}")
            return None
        except FileNotFoundError:
            print("LibreOffice not found. Please install it.")
            return None
        
        # Find the output PDF
        # It should have the same name but with .pdf extension
        base_name = os.path.splitext(original_filename)[0]
        output_filename = f"{base_name}.pdf"
        output_path = os.path.join(temp_dir, output_filename)
        
        if os.path.exists(output_path):
            with open(output_path, "rb") as f:
                return f.read()
        else:
            print(f"Output PDF not found at {output_path}")
            return None
