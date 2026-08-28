from zeaz_provider.observability import Observability


def test_prometheus_metrics_use_bounded_labels():
    metrics = Observability()
    metrics.start_request()
    metrics.finish_request(
        method="POST",
        path="/v1/messages",
        status_code=200,
        duration_seconds=0.25,
    )

    output = metrics.prometheus().decode()
    assert 'zeaz_http_requests_total{method="POST",path="/v1/messages",status="200"} 1.0' in output
    assert "zeaz_http_request_duration_seconds_sum" in output
    assert "zeaz_http_requests_in_flight 0.0" in output


def test_otlp_setup_is_opt_in(monkeypatch):
    configured: list[bool] = []
    monkeypatch.setattr(Observability, "_configure_otlp", lambda self: configured.append(True))
    Observability(otlp_enabled=False)
    Observability(otlp_enabled=True)
    assert configured == [True]
