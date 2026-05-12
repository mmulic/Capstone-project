"""
Evaluation Service (BE-020)
============================
Compares predictions against FEMA ground-truth labels.
Computes accuracy, per-class precision/recall/F1, and confusion matrix.
"""

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Prediction, GroundTruth, DamageClass


class EvaluationService:
    """Evaluates model predictions against ground truth labels."""

    async def evaluate(self, db: AsyncSession) -> dict:
        """
        Run full evaluation. Returns:
        - overall accuracy
        - per-class precision, recall, F1
        - confusion matrix
        """
        # Get latest prediction per property
        latest_preds_query = (
            select(Prediction.property_id, Prediction.damage_class, Prediction.confidence)
            .order_by(Prediction.property_id, desc(Prediction.created_at))
        )
        result = await db.execute(latest_preds_query)
        all_preds = result.all()

        # Dedupe — keep latest per property
        latest_by_prop = {}
        for prop_id, damage_class, conf in all_preds:
            if prop_id not in latest_by_prop:
                latest_by_prop[prop_id] = damage_class

        # Get all ground truth labels
        gt_result = await db.execute(
            select(GroundTruth.property_id, GroundTruth.damage_class)
        )
        ground_truth = {row[0]: row[1] for row in gt_result.all()}

        # Find matched pairs
        matched_pairs = []  # (predicted, actual)
        for prop_id, predicted in latest_by_prop.items():
            if prop_id in ground_truth:
                matched_pairs.append((predicted, ground_truth[prop_id]))

        if not matched_pairs:
            return {
                "total_predictions": len(latest_by_prop),
                "total_ground_truth": len(ground_truth),
                "matched": 0,
                "overall_accuracy": 0.0,
                "per_class": {},
                "confusion_matrix": {},
                "message": "No matched prediction/ground-truth pairs to evaluate",
            }

        # Build confusion matrix
        classes = list(DamageClass)
        confusion = {
            actual.value: {predicted.value: 0 for predicted in classes}
            for actual in classes
        }

        for predicted, actual in matched_pairs:
            confusion[actual.value][predicted.value] += 1

        # Overall accuracy
        correct = sum(1 for p, a in matched_pairs if p == a)
        overall_accuracy = correct / len(matched_pairs)

        # Per-class metrics
        per_class = {}
        for cls in classes:
            cls_val = cls.value
            tp = confusion[cls_val][cls_val]
            fp = sum(confusion[other.value][cls_val] for other in classes if other != cls)
            fn = sum(confusion[cls_val][other.value] for other in classes if other != cls)

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

            support = sum(confusion[cls_val].values())

            per_class[cls_val] = {
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1": round(f1, 4),
                "support": support,
            }

        return {
            "total_predictions": len(latest_by_prop),
            "total_ground_truth": len(ground_truth),
            "matched": len(matched_pairs),
            "overall_accuracy": round(overall_accuracy, 4),
            "per_class": per_class,
            "confusion_matrix": confusion,
        }


# Singleton
evaluation_service = EvaluationService()
