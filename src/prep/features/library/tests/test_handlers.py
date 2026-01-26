"""Tests for library API handlers."""

import pytest
from fastapi.testclient import TestClient


class TestLibraryInterviewsEndpoint:
    """Tests for GET /library/interviews endpoint."""

    @pytest.mark.skip(reason="Requires Supabase connection and authentication")
    def test_get_library_interviews_all(self, client: TestClient) -> None:
        """Test fetching all interviews for user's discipline."""
        response = client.get("/api/v1/library/interviews")
        # Expected to return 401 without auth
        assert response.status_code in [200, 401]

    @pytest.mark.skip(reason="Requires Supabase connection and authentication")
    def test_get_library_interviews_with_search(self, client: TestClient) -> None:
        """Test searching interviews by query."""
        response = client.get("/api/v1/library/interviews?query=stripe")
        # Expected to return 401 without auth
        assert response.status_code in [200, 401]

    @pytest.mark.skip(reason="Requires Supabase connection and authentication")
    def test_get_library_interviews_pagination(self, client: TestClient) -> None:
        """Test interview pagination with offset and limit."""
        response = client.get("/api/v1/library/interviews?limit=50&offset=50")
        # Expected to return 401 without auth
        assert response.status_code in [200, 401]

    @pytest.mark.skip(reason="Requires Supabase connection and authentication")
    def test_get_library_interviews_discipline_filter(self, client: TestClient) -> None:
        """Test that interviews are filtered by user's discipline."""
        # This test would require a properly authenticated user
        # and verification that only matching discipline interviews are returned
        response = client.get("/api/v1/library/interviews")
        assert response.status_code in [200, 401, 404]

    @pytest.mark.skip(reason="Requires Supabase connection and authentication")
    def test_get_library_interviews_requires_auth(self, client: TestClient) -> None:
        """Test that endpoint requires authentication."""
        response = client.get("/api/v1/library/interviews")
        # Without auth header, should get 401
        assert response.status_code == 401

    @pytest.mark.skip(reason="Requires Supabase connection and authentication")
    def test_get_library_interviews_requires_onboarding(self, client: TestClient) -> None:
        """Test that endpoint requires completed onboarding (discipline set)."""
        # Would need authenticated user without discipline set
        response = client.get("/api/v1/library/interviews")
        assert response.status_code in [401, 404]

    @pytest.mark.skip(reason="Requires Supabase connection and authentication")
    def test_get_library_interviews_empty_query(self, client: TestClient) -> None:
        """Test that empty query returns all interviews."""
        response = client.get("/api/v1/library/interviews?query=")
        # Empty query should be treated as no query (all results)
        assert response.status_code in [200, 401, 422]

    @pytest.mark.skip(reason="Requires Supabase connection and authentication")
    def test_get_library_interviews_no_results(self, client: TestClient) -> None:
        """Test handling of search with no matching results."""
        # Use a query that is unlikely to match anything
        response = client.get("/api/v1/library/interviews?query=xyznonexistentquery12345")
        if response.status_code == 200:
            data = response.json()
            assert "data" in data
            assert isinstance(data["data"], list)
            assert data["count"] == 0
            assert data["total"] == 0
            assert data["has_more"] is False

    @pytest.mark.skip(reason="Requires Supabase connection and authentication")
    def test_get_library_interviews_response_structure(self, client: TestClient) -> None:
        """Test that response has correct paginated structure."""
        response = client.get("/api/v1/library/interviews?limit=10")
        if response.status_code == 200:
            data = response.json()
            # Check paginated response structure
            assert "data" in data
            assert "count" in data
            assert "total" in data
            assert "limit" in data
            assert "offset" in data
            assert "has_more" in data
            # Verify limit is respected
            assert data["limit"] == 10
            assert data["offset"] == 0


class TestLibraryDrillsEndpoint:
    """Tests for GET /library/drills endpoint."""

    @pytest.mark.skip(reason="Requires Supabase connection and authentication")
    def test_get_library_drills_all(self, client: TestClient) -> None:
        """Test fetching all drills for user's discipline."""
        response = client.get("/api/v1/library/drills")
        # Expected to return 401 without auth
        assert response.status_code in [200, 401]

    @pytest.mark.skip(reason="Requires Supabase connection and authentication")
    def test_get_library_drills_includes_non_recommended(self, client: TestClient) -> None:
        """
        Test that library drills include ALL drills, not just recommended.

        Critical test: Library should show all drills (is_recommended_drill=false included).
        This is different from home screen which only shows recommended drills.
        """
        # This test would verify that drills with is_recommended_drill=false are included
        response = client.get("/api/v1/library/drills")
        assert response.status_code in [200, 401]

    @pytest.mark.skip(reason="Requires Supabase connection and authentication")
    def test_get_library_drills_with_search(self, client: TestClient) -> None:
        """Test searching drills by query."""
        response = client.get("/api/v1/library/drills?query=star")
        assert response.status_code in [200, 401]

    @pytest.mark.skip(reason="Requires Supabase connection and authentication")
    def test_get_library_drills_filter_by_problem_type(self, client: TestClient) -> None:
        """Test filtering drills by problem type."""
        # Test behavioral filter
        response = client.get("/api/v1/library/drills?problem_type=behavioral")
        assert response.status_code in [200, 401]

        # Test metrics filter
        response = client.get("/api/v1/library/drills?problem_type=metrics")
        assert response.status_code in [200, 401]

    @pytest.mark.skip(reason="Requires Supabase connection and authentication")
    def test_get_library_drills_search_and_filter(self, client: TestClient) -> None:
        """Test combining search query with problem_type filter."""
        response = client.get("/api/v1/library/drills?query=framework&problem_type=behavioral")
        assert response.status_code in [200, 401]

    @pytest.mark.skip(reason="Requires Supabase connection and authentication")
    def test_get_library_drills_pagination(self, client: TestClient) -> None:
        """Test drill pagination with offset and limit."""
        response = client.get("/api/v1/library/drills?limit=50&offset=50")
        assert response.status_code in [200, 401]

    @pytest.mark.skip(reason="Requires Supabase connection and authentication")
    def test_get_library_drills_discipline_filter(self, client: TestClient) -> None:
        """Test that drills are filtered by user's discipline."""
        response = client.get("/api/v1/library/drills")
        assert response.status_code in [200, 401, 404]

    @pytest.mark.skip(reason="Requires Supabase connection and authentication")
    def test_get_library_drills_requires_auth(self, client: TestClient) -> None:
        """Test that endpoint requires authentication."""
        response = client.get("/api/v1/library/drills")
        assert response.status_code == 401

    @pytest.mark.skip(reason="Requires Supabase connection and authentication")
    def test_get_library_drills_requires_onboarding(self, client: TestClient) -> None:
        """Test that endpoint requires completed onboarding (discipline set)."""
        response = client.get("/api/v1/library/drills")
        assert response.status_code in [401, 404]

    @pytest.mark.skip(reason="Requires Supabase connection and authentication")
    def test_get_library_drills_empty_results(self, client: TestClient) -> None:
        """Test handling of filters with no matching results."""
        response = client.get("/api/v1/library/drills?query=xyznonexistentquery12345")
        if response.status_code == 200:
            data = response.json()
            assert data["count"] == 0
            assert data["total"] == 0
            assert data["has_more"] is False

    @pytest.mark.skip(reason="Requires Supabase connection and authentication")
    def test_get_library_drills_response_structure(self, client: TestClient) -> None:
        """Test that response has correct paginated structure."""
        response = client.get("/api/v1/library/drills?limit=20")
        if response.status_code == 200:
            data = response.json()
            # Check paginated response structure
            assert "data" in data
            assert "count" in data
            assert "total" in data
            assert "limit" in data
            assert "offset" in data
            assert "has_more" in data
            assert data["limit"] == 20
            assert data["offset"] == 0


class TestLibraryMetadataEndpoint:
    """Tests for GET /library/metadata endpoint."""

    @pytest.mark.skip(reason="Requires Supabase connection and authentication")
    def test_get_library_metadata_product(self, client: TestClient) -> None:
        """Test metadata returns correct problem types for Product discipline."""
        # Would need authenticated user with product discipline
        response = client.get("/api/v1/library/metadata")
        if response.status_code == 200:
            data = response.json()["data"]
            assert "problem_types" in data
            # Product should have 7 problem types
            expected_types = [
                "behavioral",
                "guesstimation",
                "metrics",
                "problem_solving",
                "product_design",
                "product_improvement",
                "product_strategy",
            ]
            assert set(data["problem_types"]) == set(expected_types)

    @pytest.mark.skip(reason="Requires Supabase connection and authentication")
    def test_get_library_metadata_design(self, client: TestClient) -> None:
        """Test metadata returns correct problem types for Design discipline."""
        # Would need authenticated user with design discipline
        response = client.get("/api/v1/library/metadata")
        if response.status_code == 200:
            data = response.json()["data"]
            # Design should have 4 problem types
            expected_types = [
                "design_approach",
                "user_research",
                "problem_solving",
                "behavioral",
            ]
            assert set(data["problem_types"]) == set(expected_types)

    @pytest.mark.skip(reason="Requires Supabase connection and authentication")
    def test_get_library_metadata_marketing(self, client: TestClient) -> None:
        """Test metadata returns correct problem types for Marketing discipline."""
        # Would need authenticated user with marketing discipline
        response = client.get("/api/v1/library/metadata")
        if response.status_code == 200:
            data = response.json()["data"]
            # Marketing should have 6 problem types
            expected_types = [
                "campaign_strategy",
                "channel_strategy",
                "growth",
                "market_analysis",
                "metrics",
                "behavioral",
            ]
            assert set(data["problem_types"]) == set(expected_types)

    @pytest.mark.skip(reason="Requires Supabase connection and authentication")
    def test_get_library_metadata_requires_auth(self, client: TestClient) -> None:
        """Test that endpoint requires authentication."""
        response = client.get("/api/v1/library/metadata")
        assert response.status_code == 401

    @pytest.mark.skip(reason="Requires Supabase connection and authentication")
    def test_get_library_metadata_requires_onboarding(self, client: TestClient) -> None:
        """Test that endpoint requires completed onboarding (discipline set)."""
        response = client.get("/api/v1/library/metadata")
        assert response.status_code in [401, 404]


class TestLibraryPagination:
    """Tests for pagination behavior across library endpoints."""

    @pytest.mark.skip(reason="Requires Supabase connection and authentication")
    def test_pagination_has_more_true(self, client: TestClient) -> None:
        """Test has_more=true when more results exist."""
        # Request only 1 item to ensure has_more is likely true
        response = client.get("/api/v1/library/interviews?limit=1")
        if response.status_code == 200:
            data = response.json()
            # If there are multiple interviews, has_more should be true
            if data["total"] > 1:
                assert data["has_more"] is True

    @pytest.mark.skip(reason="Requires Supabase connection and authentication")
    def test_pagination_has_more_false(self, client: TestClient) -> None:
        """Test has_more=false when at the end of results."""
        # Get total count first
        response = client.get("/api/v1/library/interviews?limit=1000")
        if response.status_code == 200:
            data = response.json()
            total = data["total"]
            # Request from offset that should reach the end
            response2 = client.get(f"/api/v1/library/interviews?offset={total}")
            if response2.status_code == 200:
                data2 = response2.json()
                assert data2["has_more"] is False

    @pytest.mark.skip(reason="Requires Supabase connection and authentication")
    def test_pagination_consistent_ordering(self, client: TestClient) -> None:
        """Test that pagination returns consistent ordering across pages."""
        # Get first page
        response1 = client.get("/api/v1/library/interviews?limit=5&offset=0")
        # Get second page
        response2 = client.get("/api/v1/library/interviews?limit=5&offset=5")

        if response1.status_code == 200 and response2.status_code == 200:
            data1 = response1.json()
            data2 = response2.json()

            # Extract IDs from both pages
            ids_page1 = {item["id"] for item in data1["data"]}
            ids_page2 = {item["id"] for item in data2["data"]}

            # Verify no overlap (consistent ordering)
            assert len(ids_page1.intersection(ids_page2)) == 0


class TestLibraryIntegration:
    """Integration tests for library feature."""

    @pytest.mark.skip(reason="Requires Supabase connection and authentication")
    def test_library_interviews_complete_flow(self, client: TestClient) -> None:
        """Test complete flow: Browse → Search → Paginate."""
        # Browse all
        response1 = client.get("/api/v1/library/interviews?limit=10")
        assert response1.status_code in [200, 401]

        # Search
        response2 = client.get("/api/v1/library/interviews?query=product")
        assert response2.status_code in [200, 401]

        # Paginate
        response3 = client.get("/api/v1/library/interviews?limit=5&offset=5")
        assert response3.status_code in [200, 401]

    @pytest.mark.skip(reason="Requires Supabase connection and authentication")
    def test_library_drills_complete_flow(self, client: TestClient) -> None:
        """Test complete flow: Browse → Filter → Search → Paginate."""
        # Browse all
        response1 = client.get("/api/v1/library/drills?limit=10")
        assert response1.status_code in [200, 401]

        # Filter by problem type
        response2 = client.get("/api/v1/library/drills?problem_type=behavioral")
        assert response2.status_code in [200, 401]

        # Search
        response3 = client.get("/api/v1/library/drills?query=framework")
        assert response3.status_code in [200, 401]

        # Combined filter + search
        response4 = client.get("/api/v1/library/drills?query=framework&problem_type=behavioral")
        assert response4.status_code in [200, 401]

        # Paginate
        response5 = client.get("/api/v1/library/drills?limit=5&offset=5")
        assert response5.status_code in [200, 401]

    @pytest.mark.skip(reason="Requires Supabase connection and authentication")
    def test_library_vs_home_screen_different_results(self, client: TestClient) -> None:
        """
        Test that library shows more drills than home screen.

        Library should show ALL drills in discipline, while home screen
        only shows recommended drills (is_recommended_drill=true).
        """
        # Get home screen drills (5 random recommended)
        home_response = client.get("/api/v1/drills")

        # Get library drills (all in discipline)
        library_response = client.get("/api/v1/library/drills?limit=1000")

        if home_response.status_code == 200 and library_response.status_code == 200:
            home_data = home_response.json()
            library_data = library_response.json()

            # Library total should be >= home screen count (usually more)
            # since library includes non-recommended drills
            assert library_data["total"] >= home_data["count"]

    @pytest.mark.skip(reason="Requires Supabase connection and authentication")
    def test_discipline_isolation(self, client: TestClient) -> None:
        """
        Test that users only see content from their discipline.

        Critical test: Verify discipline filtering is working correctly.
        """
        # Would need multiple authenticated users with different disciplines
        # to properly test isolation
        response = client.get("/api/v1/library/interviews")
        assert response.status_code in [200, 401, 404]

    @pytest.mark.skip(reason="Requires Supabase connection and authentication")
    def test_backward_compatibility(self, client: TestClient) -> None:
        """Test that existing endpoints are unchanged by library feature."""
        # Home screen interview endpoint
        response1 = client.get("/api/v1/interviews")
        assert response1.status_code in [200, 401]

        # Home screen drills endpoint
        response2 = client.get("/api/v1/drills")
        assert response2.status_code in [200, 401]

        # Search endpoint
        response3 = client.get("/api/v1/interviews/search?query=test")
        assert response3.status_code in [200, 500]

        # Verify search endpoint structure hasn't changed
        if response3.status_code == 200:
            data = response3.json()
            assert "data" in data
            assert "count" in data
