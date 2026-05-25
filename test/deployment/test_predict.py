"""
Tests for predict() in deployment_service.

Key invariant: internal predict calls go to
    http://{container_name}:8000/predict
NOT to the Traefik endpoint_url.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.deployments.models.enums import DeploymentStatus
from src.deployments.service.deployment_service import predict

from conftest import make_deployment, make_db_for_predict


def _make_async_client(response_json: dict):
    """Return a mock httpx.AsyncClient that captures the URL it's called with."""
    captured_urls = []

    async def fake_post(url, **kwargs):
        captured_urls.append(url)
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = response_json
        return resp

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__  = AsyncMock(return_value=False)
    mock_client.post = fake_post
    return mock_client, captured_urls


@pytest.mark.asyncio
@patch("src.deployments.service.deployment_service._prepare_features", return_value=[1.0, 2.0, 3.0])
async def test_predict_url_uses_container_name_not_endpoint_url(mock_prep):
    dep = make_deployment()
    db  = make_db_for_predict(dep)
    mock_client, captured_urls = _make_async_client(
        {"prediction": [1], "prediction_label": "yes", "confidence": 0.9}
    )

    with patch("src.deployments.service.deployment_service.httpx.AsyncClient", return_value=mock_client):
        await predict(dep.id, {"age": 30}, db)

    assert len(captured_urls) == 1
    url = captured_urls[0]
    assert f"http://{dep.container_name}:8000/predict" == url, (
        f"predict() called wrong URL: {url!r}. "
        f"Should be http://{{container_name}}:8000/predict, not the Traefik endpoint_url."
    )


@pytest.mark.asyncio
@patch("src.deployments.service.deployment_service._prepare_features", return_value=[1.0])
async def test_predict_url_does_not_use_endpoint_url(mock_prep):
    dep = make_deployment()
    db  = make_db_for_predict(dep)
    mock_client, captured_urls = _make_async_client({"prediction": [0]})

    with patch("src.deployments.service.deployment_service.httpx.AsyncClient", return_value=mock_client):
        await predict(dep.id, {"x": 1}, db)

    assert dep.endpoint_url not in captured_urls[0], (
        "predict() must NOT call the Traefik endpoint_url internally — "
        "use the Docker network container_name:8000 URL instead."
    )


@pytest.mark.asyncio
async def test_predict_raises_if_deployment_not_active():
    dep = make_deployment(status=DeploymentStatus.STOPPED)

    with pytest.raises(ValueError, match="not ACTIVE"):
        await predict(dep.id, {"x": 1}, make_db_for_predict(dep))


@pytest.mark.asyncio
async def test_predict_raises_if_not_found():
    db = MagicMock()
    db.query.return_value.options.return_value.filter.return_value.first.return_value = None

    with pytest.raises(ValueError, match="not found"):
        await predict(uuid.uuid4(), {"x": 1}, db)


@pytest.mark.asyncio
@patch("src.deployments.service.deployment_service._prepare_features", return_value=[1.0])
async def test_predict_increments_total_calls(mock_prep):
    dep = make_deployment()
    assert dep.total_calls == 0
    mock_client, _ = _make_async_client({"prediction": [1]})

    with patch("src.deployments.service.deployment_service.httpx.AsyncClient", return_value=mock_client):
        await predict(dep.id, {"x": 1}, make_db_for_predict(dep))

    assert dep.total_calls == 1


@pytest.mark.asyncio
@patch("src.deployments.service.deployment_service._prepare_features", return_value=[1.0])
async def test_predict_raises_on_timeout(mock_prep):
    dep = make_deployment()
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__  = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

    with patch("src.deployments.service.deployment_service.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(RuntimeError, match="timed out"):
            await predict(dep.id, {"x": 1}, make_db_for_predict(dep))


@pytest.mark.asyncio
@patch("src.deployments.service.deployment_service._prepare_features", return_value=[1.0])
async def test_predict_raises_on_http_error(mock_prep):
    dep = make_deployment()
    err_response = MagicMock()
    err_response.text = "Internal Server Error"

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__  = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(
        side_effect=httpx.HTTPStatusError("500", request=MagicMock(), response=err_response)
    )

    with patch("src.deployments.service.deployment_service.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(RuntimeError, match="Model container returned an error"):
            await predict(dep.id, {"x": 1}, make_db_for_predict(dep))
