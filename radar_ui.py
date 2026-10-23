@'
from pathlib import Path
from datetime import datetime
import shutil
import py_compile

p = Path("radar_ui.py")
original = p.read_text(encoding="utf-8-sig")
backup_dir = Path("backups") / ("encoding_final_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
backup_dir.mkdir(parents=True, exist_ok=True)
shutil.copy2(p, backup_dir / p.name)

markers = ("Ã", "Â", "ðŸ", "â€", "âš")
fixed = []
changes = 0

def repair_line(line):
    current = line
    for _ in range(2):
        if not any(m in current for m in markers):
            break
        raw = bytearray()
        try:
            for ch in current:
                try:
                    raw.extend(ch.encode("cp1252"))
                except UnicodeEncodeError:
                    if ord(ch) <= 255:
                        raw.append(ord(ch))
                    else:
                        raise
            candidate = raw.decode("utf-8")
            if candidate == current:
                break
            current = candidate
        except (UnicodeEncodeError, UnicodeDecodeError):
            break
    return current

for line in original.splitlines(keepends=True):
    new_line = repair_line(line)
    if new_line != line:
        changes += 1
    fixed.append(new_line)

result = "".join(fixed)
p.write_text(result, encoding="utf-8", newline="")

try:
    py_compile.compile(str(p), doraise=True)
except Exception:
    shutil.copy2(backup_dir / p.name, p)
    print("ERROR: compilación fallida; se restauró el respaldo.")
    raise

print("Respaldo:", backup_dir)
print("Líneas reparadas:", changes)
print("Texto de prueba:")
for line in result.splitlines():
    if "CONCEDE AAA RADAR" in line or "Detecci" in line or "SeÃ" in line:
        print(line.strip())
print("Compilación: CORRECTA")
'@ | Set-Content .\repair_encoding_final.py -Encoding utf8

python .\repair_encoding_final.py
if ($LASTEXITCODE -eq 0) {
    Get-Content .\radar_ui.py -Raw | Set-Clipboard
    Write-Host "Archivo reparado y copiado al portapapeles."
}
