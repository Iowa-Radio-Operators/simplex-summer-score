"""
Scoring logic for Summer of Simplex.

Rules:
  - Voice Simplex contact:       1 point
  - Voice Simplex + POTA:        2 points
  - Digital contact (any mode):  1 point
  - Admin daily bonus multiplier applied per operator per day
"""

from collections import defaultdict


def score_submission(sub):
    """Return the base point value for a single submission."""
    if sub.mode_type == "voice":
        return 2 if sub.is_pota else 1
    elif sub.mode_type == "digital":
        return 1
    return 0


def score_submissions_for_operator(submissions, operator_name=None):
    """
    Score all submissions for a single operator.

    Returns:
    {
      "by_operator": {
          "total_score":      int,
          "total_contacts":   int,
          "voice_contacts":   int,
          "voice_score":      int,
          "pota_contacts":    int,
          "digital_contacts": int,
          "digital_score":    int,
          "days":             int,
      },
      "daily": {
          date: {
              "voice":    [ {sub, score}, ... ],
              "digital":  [ {sub, score}, ... ],
              "score":    int,
              "multiplier":        float,
              "multiplier_reason": str|None,
          },
          ...
      }
    }
    """
    from .models import ScoreMultiplier

    # Load any admin-applied daily bonus multipliers
    daily_bonuses = {}
    if operator_name:
        bonuses = ScoreMultiplier.query.filter_by(operator=operator_name).all()
        for bonus in bonuses:
            daily_bonuses[bonus.date] = {
                "multiplier": bonus.multiplier,
                "reason":     bonus.reason,
            }

    # Filter deleted, group by date
    active = [s for s in submissions if not s.is_deleted]

    by_date = defaultdict(list)
    for sub in active:
        date_key = sub.submitted_at.date() if sub.submitted_at else None
        if date_key:
            by_date[date_key].append(sub)

    daily_results = {}
    total_score         = 0
    total_contacts      = 0
    voice_contacts      = 0
    voice_score         = 0
    pota_contacts       = 0
    digital_contacts    = 0
    digital_score       = 0

    for date in sorted(by_date.keys()):
        day_subs = by_date[date]
        bonus    = daily_bonuses.get(date, {"multiplier": 1.0, "reason": None})
        mult     = bonus["multiplier"]

        day_voice   = []
        day_digital = []
        day_score   = 0

        for sub in day_subs:
            base  = score_submission(sub)
            score = base * mult

            if sub.mode_type == "voice":
                day_voice.append({"sub": sub, "score": score})
                voice_contacts += 1
                voice_score    += score
                if sub.is_pota:
                    pota_contacts += 1
            elif sub.mode_type == "digital":
                day_digital.append({"sub": sub, "score": score})
                digital_contacts += 1
                digital_score    += score

            day_score      += score
            total_contacts += 1

        total_score += day_score

        daily_results[date] = {
            "voice":             day_voice,
            "digital":           day_digital,
            "score":             day_score,
            "multiplier":        mult,
            "multiplier_reason": bonus["reason"],
        }

    return {
        "daily": daily_results,
        "by_operator": {
            "total_score":      total_score,
            "total_contacts":   total_contacts,
            "voice_contacts":   voice_contacts,
            "voice_score":      voice_score,
            "pota_contacts":    pota_contacts,
            "digital_contacts": digital_contacts,
            "digital_score":    digital_score,
            "days":             len(by_date),
        },
    }