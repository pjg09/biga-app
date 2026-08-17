"""Reintento con backoff del adaptador de correo.

Se prueba con un doble y no contra el proveedor real a propósito: el sandbox
gratuito de Mailtrap responde `550 Too many emails per second` incluso con 8
segundos entre envíos —su cuota de plan está agotada, no su ritmo—, así que un
test contra él mediría el plan del proveedor, no este código.
"""
import pytest

from app.adapters.email.retrying import RetryingEmailAdapter, is_transient


class FakeAdapter:
    """Rechaza los primeros `fallos_iniciales` envíos con el error indicado."""

    def __init__(self, fallos_iniciales=0, error="550 Too many emails per second"):
        self.fallos_iniciales = fallos_iniciales
        self.error = error
        self.intentos = 0
        self.enviados = []

    def send(self, to, subject, html):
        self.intentos += 1
        if self.intentos <= self.fallos_iniciales:
            raise RuntimeError(self.error)
        self.enviados.append(to)


@pytest.fixture(autouse=True)
def sin_esperas(monkeypatch):
    """Anula el sleep: se comprueba la política de reintento, no el reloj."""
    monkeypatch.setattr("app.adapters.email.retrying.time.sleep", lambda _: None)


def test_reintenta_y_acaba_enviando():
    """El caso que motivó todo: el proveedor rechaza por tasa y al reintentar
    acepta. Sin esto, el aviso se perdía — un FAILED no se reencola."""
    inner = FakeAdapter(fallos_iniciales=2)
    RetryingEmailAdapter(inner, attempts=3, base_delay=0.01).send("a@b.co", "s", "<p>h</p>")

    assert inner.intentos == 3
    assert inner.enviados == ["a@b.co"]


def test_no_reintenta_errores_permanentes():
    """Una dirección inválida no mejora esperando: gastar intentos en ella
    retrasa la cola y esconde el error real tras un log repetido."""
    inner = FakeAdapter(fallos_iniciales=99, error="550 invalid recipient address")

    with pytest.raises(RuntimeError):
        RetryingEmailAdapter(inner, attempts=4, base_delay=0.01).send("mal", "s", "<p>h</p>")

    assert inner.intentos == 1


def test_propaga_el_error_original_al_agotar_intentos():
    """El notifier registra ese texto como `error_message`: si el wrapper lo
    reemplazara, la consola mostraría un error del wrapper y no del proveedor."""
    inner = FakeAdapter(fallos_iniciales=99)

    with pytest.raises(RuntimeError, match="Too many emails"):
        RetryingEmailAdapter(inner, attempts=3, base_delay=0.01).send("a@b.co", "s", "<p>h</p>")

    assert inner.intentos == 3


def test_backoff_crece_y_lleva_jitter(monkeypatch):
    """Exponencial para dar tiempo al proveedor, con jitter para que dos envíos
    que chocaron con el mismo límite no reintenten exactamente a la vez."""
    esperas = []
    monkeypatch.setattr("app.adapters.email.retrying.time.sleep", esperas.append)
    inner = FakeAdapter(fallos_iniciales=99)

    with pytest.raises(RuntimeError):
        RetryingEmailAdapter(inner, attempts=4, base_delay=1.0).send("a@b.co", "s", "<p>h</p>")

    assert len(esperas) == 3
    assert esperas[0] < esperas[1] < esperas[2]      # crece
    assert not any(e == int(e) for e in esperas)     # ninguna es el valor exacto: hay jitter


@pytest.mark.parametrize("mensaje", [
    "550 Too many emails per second", "429 rate limit exceeded",
    "Connection reset by peer", "503 Service Unavailable", "Read timed out",
])
def test_marcadores_transitorios(mensaje):
    assert is_transient(RuntimeError(mensaje))


@pytest.mark.parametrize("mensaje", [
    "550 invalid recipient", "401 unauthorized: bad api key", "domain not verified",
])
def test_marcadores_permanentes(mensaje):
    assert not is_transient(RuntimeError(mensaje))
