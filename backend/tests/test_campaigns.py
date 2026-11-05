"""Campaign, tracked-link, click recording, and first-party analytics coverage."""

from fastapi.testclient import TestClient

from tests.test_personas import _login


def test_campaign_link_redirect_records_real_click_and_analytics(client: TestClient) -> None:
    _login(client)
    campaign = client.post(
        "/api/v1/campaigns",
        json={
            "name": "Spring launch",
            "platform": "facebook",
            "destination_url": "https://example.com/landing",
        },
    )
    assert campaign.status_code == 201
    campaign_id = campaign.json()["id"]
    assert (
        client.patch(
            f"/api/v1/campaigns/{campaign_id}/status", json={"status": "active"}
        ).status_code
        == 200
    )

    link = client.post(
        f"/api/v1/campaigns/{campaign_id}/links",
        json={
            "label": "Story link",
            "affiliate_url": "https://shop.example.com/product?ref=affiliate",
            "utm_source": "facebook",
            "utm_medium": "social",
        },
    )
    assert link.status_code == 201
    body = link.json()
    assert body["tracking_path"] == f"/r/{body['tracking_id']}"
    assert "utm_source=facebook" in body["destination_url"]
    assert f"wbot_tracking_id={body['tracking_id']}" in body["destination_url"]

    redirect = client.get(body["tracking_path"], follow_redirects=False)
    assert redirect.status_code == 302
    assert redirect.headers["location"].startswith("https://shop.example.com/product")
    assert redirect.headers["cache-control"] == "no-store"

    analytics = client.get("/api/v1/analytics")
    assert analytics.status_code == 200
    data = analytics.json()
    assert data["summary"]["total_clicks"] == 1
    assert data["summary"]["tracked_links"] == 1
    assert data["summary"]["active_campaigns"] == 1
    assert data["campaign_performance"][0]["clicks"] == 1
    assert data["link_performance"][0]["clicks"] == 1
    assert sum(point["value"] for point in data["clicks_by_day"]) == 1


def test_campaign_and_links_are_owner_scoped(client: TestClient) -> None:
    _login(client)
    campaign = client.post("/api/v1/campaigns", json={"name": "Private campaign"})
    assert campaign.status_code == 201
    campaign_id = campaign.json()["id"]
    assert (
        client.post(
            f"/api/v1/campaigns/{campaign_id}/links",
            json={"label": "Link", "affiliate_url": "https://example.com/a"},
        ).status_code
        == 201
    )

    _login(client, "campaign-other@example.com", "other-secret")
    assert client.get("/api/v1/campaigns").json()["total"] == 0
    assert client.get(f"/api/v1/campaigns/{campaign_id}").status_code == 404
    assert client.get(f"/api/v1/campaigns/{campaign_id}/links").status_code == 404
    assert (
        client.post(
            f"/api/v1/campaigns/{campaign_id}/links",
            json={"label": "Nope", "affiliate_url": "https://example.com/b"},
        ).status_code
        == 404
    )


def test_invalid_destination_url_is_rejected(client: TestClient) -> None:
    _login(client)
    response = client.post(
        "/api/v1/campaigns",
        json={"name": "Bad URL", "destination_url": "javascript:alert(1)"},
    )
    assert response.status_code == 409
    campaign = client.post("/api/v1/campaigns", json={"name": "Valid campaign"}).json()
    link = client.post(
        f"/api/v1/campaigns/{campaign['id']}/links",
        json={"label": "Bad", "affiliate_url": "ftp://example.com/file"},
    )
    assert link.status_code == 409


def test_unknown_tracking_id_returns_404(client: TestClient) -> None:
    assert client.get("/r/doesnotexist123", follow_redirects=False).status_code == 404
