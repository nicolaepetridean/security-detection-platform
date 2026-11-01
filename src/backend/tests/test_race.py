"""The race condition: two analysts claim the SAME detection simultaneously.

Expectation from the brief: exactly one succeeds, the other gets clear feedback.
We fire both claims from threads against a shared SQLite file and assert exactly one
200 and one 409.
"""
import threading

from conftest import auth_header, token_for


def test_simultaneous_claims_exactly_one_wins(client, seeded):
    cid = seeded["customer"].id
    detection_id = client.post(
        "/ingest", json={"customer_id": cid, "fields": {"event_type": "auth_fail"}}
    ).json()["detection_id"]

    # Two DIFFERENT analysts so we exercise the claim race, not the one-active index.
    alice = token_for(client, "alice")
    bob = token_for(client, "bob")

    results: list[int] = []
    barrier = threading.Barrier(2)

    def claim(token: str):
        barrier.wait()  # release both threads as close to simultaneously as possible
        resp = client.post(
            f"/detections/{detection_id}/claim", headers=auth_header(token)
        )
        results.append(resp.status_code)

    threads = [
        threading.Thread(target=claim, args=(alice,)),
        threading.Thread(target=claim, args=(bob,)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sorted(results) == [200, 409], f"expected one winner, got {results}"
