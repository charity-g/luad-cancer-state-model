"""
Arize Phoenix instrumentation for the LUAD agent pipeline.
"""

import os


def init_tracing():
    api_key = os.environ.get("PHOENIX_API_KEY")
    if not api_key:
        print("[observability] PHOENIX_API_KEY not set -- tracing disabled.")
        return None

    from phoenix.otel import register
    from openinference.instrumentation.anthropic import AnthropicInstrumentor

    os.environ["PHOENIX_CLIENT_HEADERS"] = f"api_key={api_key}"

    tracer_provider = register(
        project_name="luad-cancer-state-model",
        endpoint="https://app.phoenix.arize.com/v1/traces",
    )

    AnthropicInstrumentor().instrument(tracer_provider=tracer_provider)

    print("[observability] Phoenix tracing enabled -> https://app.phoenix.arize.com")
    return tracer_provider


from opentelemetry import trace

_tracer = trace.get_tracer("luad-cancer-state-model")


def traced_cypher_run(cypher_query, run_fn, *args, **kwargs):
    with _tracer.start_as_current_span("cypher.run_read") as span:
        span.set_attribute("cypher.query", cypher_query)
        result = run_fn(*args, **kwargs)
        span.set_attribute("cypher.rows_returned", len(result.get("rows", [])))
        return result


def traced_drug_routing(mutation, route_fn, *args, **kwargs):
    with _tracer.start_as_current_span("drug_routing.route") as span:
        span.set_attribute("mutation", mutation)
        result = route_fn(*args, **kwargs)
        if isinstance(result, dict):
            span.set_attribute("used_ml_fallback", result.get("needs_ml_fallback", False))
            span.set_attribute("database_drug_count", len(result.get("database_drugs", [])))
            span.set_attribute("model_predicted_count", len(result.get("ml_predictions", [])))
        return result
