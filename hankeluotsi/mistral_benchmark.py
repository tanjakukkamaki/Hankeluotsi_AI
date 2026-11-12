"""Explicit cloud collector reusing frozen fictional manifests and blinded review."""

import argparse
import hashlib
from pathlib import Path

from hankeluotsi import model_quality as q
from hankeluotsi.mistral_client import CloudConsent, CloudError, MistralTransport, check_configuration


class MistralProvider:
    provider = "mistral"
    measure_latency = True

    def __init__(self, consent):
        consent.require()
        self.requested_model = check_configuration()
        self.consent = consent
        self.errors = {}

    def generate(self, request, manifest):
        try:
            return MistralTransport(self.requested_model, self.consent,
                timeout=manifest.settings.timeout_seconds).complete(
                    request.messages, manifest.response_format,
                    temperature=manifest.settings.temperature, max_tokens=manifest.settings.max_tokens)
        except CloudError as error:
            self.errors[request.request_sha256] = error.code
            return q.Reply(error="timeout" if error.code == "timeout" else "request_failed")


def collect(manifest, output, consent):
    """No project/database input; exact reviewed fictional manifest is mandatory."""
    # Validate even programmatic entry points, not only CLI-loaded manifests.
    expected = q.create_manifest(manifest.settings)
    for field in ("requests", "cases", "code_sha256", "response_format", "dataset_sha256",
                  "rubric_sha256", "schema_sha256", "prompt_version", "base_prompt_version", "rubric"):
        if getattr(manifest, field) != getattr(expected, field):
            raise ValueError("Only the frozen fictional benchmark manifest may be collected")
    if output.exists():
        raise FileExistsError("Choose a new benchmark output directory")
    provider = MistralProvider(consent)
    report = q.run(manifest, provider, checkpoint=output / "attempts")
    for attempt in report["attempts"]:
        error_type = provider.errors.get(attempt["request_sha256"])
        if error_type is None:
            if attempt["incomplete_output"]:
                error_type = "incomplete"
            elif not attempt["json_valid"]:
                error_type = "invalid_json"
            elif not attempt["pydantic_valid"]:
                error_type = "invalid_schema"
        attempt["error_type"] = error_type
    report["collector"] = {"version": "mistral_collector_v1", "source_sha256": {
        name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
        for name in ("mistral_client.py", "mistral_benchmark.py")},
        "cloud_consent": True, "fictional_only": True, "automatic_retries": 0,
        "cost_note": "Unknown: no verified pricing or uncached billing basis supplied."}
    q.write_new(output / "results.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Mistral fictional-only benchmark. Explicit runs may incur charges.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute-cloud", action="store_true", required=True)
    parser.add_argument("--fictional-only", action="store_true", required=True)
    parser.add_argument("--accept-costs", action="store_true", required=True)
    args = parser.parse_args(argv)
    try:
        collect(q.load_manifest(args.manifest), args.output,
            CloudConsent(fictional_data=args.fictional_only, cloud_processing=args.execute_cloud and args.accept_costs))
    except CloudError as error:
        parser.exit(2, str(error) + "\n")
    except (ValueError, OSError, KeyError, TypeError):
        parser.exit(2, "Benchmark rejected. Check frozen fictional manifest, settings and new output path.\n")


if __name__ == "__main__":
    main()
