package cli

import "testing"

func TestComputeHalfRatio_Boundary(t *testing.T) {
	if got := computeHalfRatio(300, 389); got >= 1.3 {
		t.Fatalf("expected ratio < 1.3 for 389/300, got %.4f", got)
	}
	if got := computeHalfRatio(300, 390); got < 1.3 {
		t.Fatalf("expected ratio >= 1.3 for 390/300, got %.4f", got)
	}
	if got := computeHalfRatio(0, 10); got <= 1.3 {
		t.Fatalf("expected large ratio when firstHalf is zero and secondHalf positive, got %.4f", got)
	}
}

func TestComputeSearchDiffRatio_Boundary(t *testing.T) {
	// 31% should fail (diff ratio > 0.30)
	if got := computeSearchDiffRatio(100, 69); got <= 0.30 {
		t.Fatalf("expected diff ratio > 0.30 for 100 vs 69, got %.4f", got)
	}
	// 30% should pass (diff ratio <= 0.30)
	if got := computeSearchDiffRatio(100, 70); got > 0.30 {
		t.Fatalf("expected diff ratio <= 0.30 for 100 vs 70, got %.4f", got)
	}
}

