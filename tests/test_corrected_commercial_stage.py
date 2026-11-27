from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.analytics.release_validation import read_json
from src.pipeline import write_json
from src.synthetic.corrected_commercial_stage import FILES, approved_inputs, build, validate_serialized
from src.synthetic.marketplace_scope_validation import require_exact_approval
from src.synthetic.listing_stage import readiness

ROOT=Path(__file__).resolve().parents[1]


class CorrectedCommercialStageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.context=approved_inputs(ROOT)

    def test_exact_approval_cannot_transfer_to_changed_commercial_values(self):
        _,scope,_,_,_,approval,_,_,_=self.context
        with self.assertRaisesRegex(ValueError,"EXACT_SCOPE_APPROVAL_REQUIRED"):
            require_exact_approval({**scope["package"],"configuration_fingerprint":"changed"},approval)
        self.assertEqual(readiness(ROOT)["status"],"blocked")
        self.assertEqual(readiness(ROOT)["backend_import"],"blocked")

    def test_actual_scoped_serialization_reports_fulfillment_and_rejects_changes(self):
        with TemporaryDirectory() as work:
            location=Path(work)
            result, quality, _, _=build(ROOT,location,self.context)
            self.assertEqual(result["feasible_allocated_responses"],835)
            self.assertEqual(result["scope_counts"]["responses"],{"0":113,"1":166,"2":168,"3":111})
            self.assertEqual(quality["scope_denominators"]["products"],279)
            file=location/FILES["offers"]
            payload=read_json(file)
            row=payload["records"][0]
            row["extended_product_value"]="0.01"
            write_json(file,payload)
            with self.assertRaisesRegex(ValueError,"SCOPED_EXTENDED_VALUE_MISMATCH"):
                validate_serialized(ROOT,location,self.context)
