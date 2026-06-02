"""
speak_time.py — Dice la hora actual en voz alta usando Piper TTS + PipeWire.

Dependencias:
    pip install piper-tts typer
    sudo dnf install pulseaudio-utils pipewire-utils
"""

import datetime
import subprocess
import tempfile
from pathlib import Path

import typer

app = typer.Typer(help="Dice la hora actual de forma hablada usando Piper TTS.")

# ---------------------------------------------------------------------------
# Voces disponibles en Piper para español
# Fuente: https://huggingface.co/rhasspy/piper-voices
# ---------------------------------------------------------------------------
VOCES = {
    "es_MX-claude-high": {
        "onnx": "es/es_MX/claude/high/es_MX-claude-high.onnx",
        "json": "es/es_MX/claude/high/es_MX-claude-high.onnx.json",
    },
    "es_MX-ald-medium": {
        "onnx": "es/es_MX/ald/medium/es_MX-ald-medium.onnx",
        "json": "es/es_MX/ald/medium/es_MX-ald-medium.onnx.json",
    },
    "es_ES-carlfm-x_low": {
        "onnx": "es/es_ES/carlfm/x_low/es_ES-carlfm-x_low.onnx",
        "json": "es/es_ES/carlfm/x_low/es_ES-carlfm-x_low.onnx.json",
    },
    "es_ES-davefx-medium": {
        "onnx": "es/es_ES/davefx/medium/es_ES-davefx-medium.onnx",
        "json": "es/es_ES/davefx/medium/es_ES-davefx-medium.onnx.json",
    },
    "es_ES-sharvard-medium": {
        "onnx": "es/es_ES/sharvard/medium/es_ES-sharvard-medium.onnx",
        "json": "es/es_ES/sharvard/medium/es_ES-sharvard-medium.onnx.json",
    },
}

HF_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
MODELOS_DIR = Path.home() / ".local" / "share" / "piper-voices"


# ---------------------------------------------------------------------------
# Texto de la hora
# ---------------------------------------------------------------------------


def _hora_en_palabras(dt: datetime.datetime) -> str:
    h = dt.hour
    m = dt.minute
    periodo = "de la mañana" if h < 12 else "de la tarde" if h < 20 else "de la noche"
    h12 = h % 12 or 12
    sig = (h % 12) + 1 or 12

    if m == 0:
        frase = f"Son las {h12} en punto {periodo}"
    elif m == 1:
        frase = f"Son las {h12} y un minuto {periodo}"
    elif m < 30:
        frase = f"Son las {h12} y {m} minutos {periodo}"
    elif m == 30:
        frase = f"Son las {h12} y media {periodo}"
    elif m == 45:
        frase = f"Son cuarto para las {sig} {periodo}"
    else:
        falta = 60 - m
        frase = f"Faltan {falta} minutos para las {sig} {periodo}"

    if h in (1, 13):
        frase = frase.replace("Son las", "Es la")

    return frase


# ---------------------------------------------------------------------------
# Descarga de modelos Piper
# ---------------------------------------------------------------------------


def _descargar_modelo(nombre_voz: str) -> tuple[Path, Path]:
    """Descarga el modelo .onnx y .json si no existe. Retorna sus rutas."""
    if nombre_voz not in VOCES:
        typer.echo(f"❌ Voz '{nombre_voz}' no reconocida. Usa 'voces' para ver opciones.", err=True)
        raise typer.Exit(1)

    MODELOS_DIR.mkdir(parents=True, exist_ok=True)
    rutas = VOCES[nombre_voz]
    onnx_path = MODELOS_DIR / f"{nombre_voz}.onnx"
    json_path = MODELOS_DIR / f"{nombre_voz}.onnx.json"

    for path, key in [(onnx_path, "onnx"), (json_path, "json")]:
        if not path.exists():
            url = f"{HF_BASE}/{rutas[key]}"
            typer.echo(f"⬇ Descargando {path.name} ...")
            subprocess.run(["wget", "-q", "-O", str(path), url], check=True)

    return onnx_path, json_path


# ---------------------------------------------------------------------------
# Síntesis con Piper → WAV temporal
# ---------------------------------------------------------------------------


def _sintetizar_wav(texto: str, onnx: Path, velocidad: float) -> Path:
    """Sintetiza texto a WAV usando piper."""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    wav_path = Path(tmp.name)

    try:
        proc = subprocess.run(
            [
                "piper",
                "--model",
                str(onnx),
                "--length-scale",
                str(round(1.0 / velocidad, 3)),  # >1 = más lento
                "--output_file",
                str(wav_path),
            ],
            input=texto,
            text=True,
            capture_output=True,
        )
        if proc.returncode != 0:
            typer.echo(f"❌ Error en piper:\n{proc.stderr}", err=True)
            raise typer.Exit(1)
    except FileNotFoundError:
        typer.echo("❌ piper no encontrado. Instálalo con: pip install piper-tts", err=True)
        raise typer.Exit(1)

    return wav_path


# ---------------------------------------------------------------------------
# Reproducción con pw-cat
# ---------------------------------------------------------------------------


def _listar_sinks() -> list[dict]:
    try:
        out = subprocess.check_output(["pactl", "list", "short", "sinks"], text=True)
    except FileNotFoundError:
        typer.echo("❌ pactl no encontrado. Instálalo con: sudo dnf install pulseaudio-utils", err=True)
        raise typer.Exit(1)

    sinks = []
    for line in out.strip().splitlines():
        partes = line.split("\t")
        if len(partes) >= 2:
            sinks.append(
                {
                    "id": partes[0].strip(),
                    "nombre": partes[1].strip(),
                    "estado": partes[4].strip() if len(partes) > 4 else "",
                }
            )
    return sinks


def _reproducir(wav: Path, dispositivo: str | None) -> None:
    cmd = ["pw-cat", "--playback"]
    if dispositivo:
        cmd += ["--target", dispositivo]
    cmd.append(str(wav))

    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError:
        typer.echo("❌ pw-cat no encontrado. Instálalo con: sudo dnf install pipewire-utils", err=True)
        raise typer.Exit(1)
    finally:
        wav.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Comandos CLI
# ---------------------------------------------------------------------------


@app.command()
def voces():
    """Lista las voces en español disponibles para Piper."""
    typer.echo("\n🗣 Voces Piper disponibles:\n")
    for nombre in VOCES:
        descargada = (MODELOS_DIR / f"{nombre}.onnx").exists()
        estado = "✔ descargada" if descargada else "  no descargada"
        typer.echo(f"  {estado}  {nombre}")
    typer.echo()


@app.command()
def listar():
    """Lista los dispositivos de audio disponibles (sinks via pactl)."""
    sinks = _listar_sinks()
    if not sinks:
        typer.echo("⚠ No se encontraron sinks de audio.")
        raise typer.Exit(1)

    typer.echo("\n🔊 Sinks de audio disponibles:\n")
    for s in sinks:
        typer.echo(f"  [{s['id']}] {s['nombre']}  ({s['estado']})")
    typer.echo()


@app.command()
def hablar(
    dispositivo: str = typer.Option(
        None,
        "--dispositivo",
        "-d",
        help="Nombre del sink (usa 'listar'). Sin valor usa el sink por defecto.",
    ),
    voz: str = typer.Option(
        "es_MX-claude-high",
        "--voz",
        "-z",
        help="Voz Piper a usar (usa 'voces' para ver opciones).",
    ),
    velocidad: float = typer.Option(
        1.0,
        "--velocidad",
        "-v",
        help="Velocidad del habla. 1.0 = normal, 1.2 = más rápido, 0.8 = más lento.",
    ),
    texto_extra: str = typer.Option(
        None,
        "--texto",
        "-t",
        help="Texto adicional que se dirá después de la hora.",
    ),
):
    """Dice la hora actual en voz alta usando Piper TTS."""
    now = datetime.datetime.now()
    mensaje = _hora_en_palabras(now)
    if texto_extra:
        mensaje += f". {texto_extra}"

    typer.echo(f"🕐 {mensaje}")

    onnx, _ = _descargar_modelo(voz)
    wav = _sintetizar_wav(mensaje, onnx, velocidad)
    _reproducir(wav, dispositivo)


if __name__ == "__main__":
    app()
