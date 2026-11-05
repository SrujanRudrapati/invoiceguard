"""Named extraction systems, shared by the eval and the processing step."""

from collections.abc import Callable

from invoiceguard.cascade import cascade_extractor
from invoiceguard.config import HAIKU_MODEL, SONNET_MODEL
from invoiceguard.pipeline import Extractor, baseline_extractor, llm_extractor
from invoiceguard.replay import REPLAY_LABEL, replay_extractor

# Built lazily so `baseline` never needs an API key.
SYSTEMS: dict[str, Callable[[], Extractor]] = {
    "baseline": lambda: baseline_extractor,
    "haiku": lambda: llm_extractor(HAIKU_MODEL),
    "sonnet": lambda: llm_extractor(SONNET_MODEL),
    "cascade": cascade_extractor,
    "replay": replay_extractor,  # recorded model responses (mocked), no API key, $0
}
SYSTEM_MODELS = {"baseline": "regex", "haiku": HAIKU_MODEL, "sonnet": SONNET_MODEL,
                 "cascade": f"{HAIKU_MODEL}->{SONNET_MODEL}",
                 "replay": f"{REPLAY_LABEL}: cascade v4"}
