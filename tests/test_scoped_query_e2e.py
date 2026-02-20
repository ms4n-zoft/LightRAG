#!/usr/bin/env python3
"""
End-to-end scoped recommendation validation for partner scoping.

What this script does:
1. Calls LightRAG `/query` with `partner_id="peko"`
2. Prompts LLM to return product recommendations as strict JSON (with product_id + weburl)
3. Validates each recommended product against MongoDB `PekoPartnerDB.products`
4. Produces machine-readable results and a markdown test report in /docs

Usage:
    venv/bin/python tests/test_scoped_query_e2e.py
    venv/bin/python tests/test_scoped_query_e2e.py --max-cases 20 --max-recos 8
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import requests
from pymongo import MongoClient


DEFAULT_BASE_URL = "http://localhost:9621"
DEFAULT_API_KEY = "792IOIM4luYy/Wh4qsnGm/jlZwOVHS8jI8b4FJ8Nco4="
DEFAULT_PARTNER_ID = "peko"
DEFAULT_MONGO_URI = "mongodb://localhost:27017/?directConnection=true"
DEFAULT_MONGO_DB = "PekoPartnerDB"
DEFAULT_MONGO_COLLECTION = "products"


def normalize_weburl(url: str | None) -> str | None:
    if not url:
        return None
    value = url.strip().lower()
    value = re.sub(r"^https?://", "", value)
    value = value.rstrip("/")
    return value


def format_latency(latency_ms: float) -> str:
    """Format latency: seconds if <60s, min:sec if >=60s"""
    seconds = latency_ms / 1000.0
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)
    return f"{minutes}:{remaining_seconds:02d}"


def extract_json_object(text: str) -> dict[str, Any] | None:
    if not text:
        return None

    text = text.strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        snippet = text[start : end + 1]
        try:
            parsed = json.loads(snippet)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return None
    return None


def ensure_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def build_test_cases() -> list[dict[str, str]]:
    return [
        {
            "id": "C01",
            "category": "CRM",
            "query": "Need CRM for SMB sales team of 12 with email automation, pipeline forecasting, and simple onboarding.",
        },
        {
            "id": "C02",
            "category": "Security",
            "query": "Looking for SASE and secure web gateway for 300-user remote-first company with compliance needs.",
        },
        {
            "id": "C03",
            "category": "HR",
            "query": "We want HRIS + payroll + leave management for a 90-person startup growing across 3 countries.",
        },
        {
            "id": "C04",
            "category": "Project Management",
            "query": "Need project management with agile boards, Gantt views, and client collaboration for agency workflows.",
        },
        {
            "id": "C05",
            "category": "Accounting",
            "query": "Need accounting platform with invoicing, expense tracking, and tax reports for small business.",
        },
        {
            "id": "C06",
            "category": "ITSM",
            "query": "Need IT service desk with incident workflows, SLA tracking, and knowledge base for 200 employees.",
        },
        {
            "id": "C07",
            "category": "Marketing",
            "query": "Need multichannel marketing automation with segmentation, drip campaigns, and attribution.",
        },
        {
            "id": "C08",
            "category": "Data & BI",
            "query": "Need BI tool for dashboards, ad-hoc SQL analysis, and role-based access for business users.",
        },
        {
            "id": "C09",
            "category": "Collaboration",
            "query": "Need team collaboration suite with chat, docs, and video for distributed 500-person org.",
        },
        {
            "id": "C10",
            "category": "Dev Tools",
            "query": "Need CI/CD and code quality tooling with GitHub integration for a 35-engineer team.",
        },
        {
            "id": "C11",
            "category": "Ecommerce",
            "query": "Need ecommerce platform with B2B catalog pricing, payment gateways, and ERP integration.",
        },
        {
            "id": "C12",
            "category": "Out-of-Scope Mix",
            "query": "Recommend best gaming engine and 3D animation pipeline tools with studio rendering workflows.",
        },
        {
            "id": "C13",
            "category": "Out-of-Scope Mix",
            "query": "Need hospital patient records system with telemedicine and claims handling integration.",
        },
        {
            "id": "C14",
            "category": "Integration Heavy",
            "query": "Need CRM integrated with Slack, Microsoft Teams, Jira, HubSpot, and Salesforce migration support.",
        },
        {
            "id": "C15",
            "category": "RFP Style",
            "query": "RFP: 800 users, SOC2, SSO/SAML, audit logs, API-first, multilingual support, and granular RBAC.",
        },
        {
            "id": "C16",
            "category": "Team Size Small",
            "query": "Need simple all-in-one operations software for 8-person startup with low budget.",
        },
        {
            "id": "C17",
            "category": "Team Size Enterprise",
            "query": "Need enterprise service platform for 5,000 employees with governance, integrations, and support SLAs.",
        },
        {
            "id": "C18",
            "category": "Use Case Support",
            "query": "Need customer support platform with omnichannel ticketing, chatbot, and CSAT analytics.",
        },
        {
            "id": "C19",
            "category": "Use Case Sales",
            "query": "Need sales engagement suite with cadence automation, call intelligence, and revenue forecasting.",
        },
        {
            "id": "C20",
            "category": "Use Case Compliance",
            "query": "Need GRC and compliance tooling for ISO27001 workflows, risk registers, and evidence collection.",
        },
        {
            "id": "C21",
            "category": "Cloud Infra",
            "query": "Need cloud cost optimization and observability platform across AWS and Azure for platform team.",
        },
        {
            "id": "C22",
            "category": "Education",
            "query": "Need LMS for corporate training with certifications, learning paths, and HRIS integration.",
        },
        {
            "id": "C23",
            "category": "Procurement",
            "query": "Need procurement platform for approvals, vendor onboarding, and spend analytics.",
        },
        {
            "id": "C24",
            "category": "Knowledge Management",
            "query": "Need internal knowledge base with strong search, permissions, and documentation lifecycle controls.",
        },
    ]


@dataclass
class ValidationResult:
    product_id: str | None
    weburl: str | None
    exists_by_id: bool
    exists_by_url: bool
    id_url_same_product: bool
    is_valid_in_peko_scope: bool
    reason: str


class ScopedE2EValidator:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        partner_id: str,
        mongo_uri: str,
        mongo_db: str,
        mongo_collection: str,
        max_recos: int,
        timeout: int,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.partner_id = partner_id
        self.mongo_uri = mongo_uri
        self.mongo_db = mongo_db
        self.mongo_collection = mongo_collection
        self.max_recos = max_recos
        self.timeout = timeout

        self.headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key,
        }

        self.id_to_product: dict[str, dict[str, Any]] = {}
        self.url_to_products: dict[str, list[dict[str, Any]]] = {}

    def load_peko_scope_products(self) -> None:
        client = MongoClient(self.mongo_uri)
        try:
            collection = client[self.mongo_db][self.mongo_collection]
            products = list(collection.find({}, {"_id": 1, "weburl": 1, "name": 1, "title": 1}))

            for product in products:
                product_id = str(product.get("_id", "")).strip()
                if product_id:
                    self.id_to_product[product_id] = product

                url = normalize_weburl(product.get("weburl"))
                if url:
                    self.url_to_products.setdefault(url, []).append(product)
        finally:
            client.close()

    # Output formatting goes in user_prompt so it doesn't pollute keyword extraction
    OUTPUT_INSTRUCTIONS = (
        "Return ONLY valid JSON. No markdown, no code fences, no extra text.\n"
        "Each product in your context has a product_id (24-char hex MongoDB ObjectId). "
        "Find it in source references like product_id:<hex_id>:source:... and include the exact product_id.\n\n"
        "Output schema:\n"
        '{"query_summary": "string", "recommendations": [{"product_id": "24-char hex id", '
        '"product_name": "string", "reasoning": "string"}]}\n\n'
        "Return 3 to 8 recommendations. Only recommend products whose product_id you found in the context."
    )

    def call_query_endpoint(self, query: str) -> tuple[int, float, dict[str, Any] | None, str]:
        payload = {
            "query": query,
            "mode": "hybrid",
            "top_k": 60,
            "chunk_top_k": 30,
            "partner_id": self.partner_id,
            "response_type": "JSON",
            "user_prompt": self.OUTPUT_INSTRUCTIONS,
            "max_entity_tokens": 16000,
            "max_relation_tokens": 16000,
            "max_total_tokens": 64000,
        }

        start = time.perf_counter()
        response = requests.post(
            f"{self.base_url}/query",
            json=payload,
            headers=self.headers,
            timeout=self.timeout,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        if response.status_code != 200:
            return response.status_code, elapsed_ms, None, response.text

        body = response.json()
        llm_response = body.get("response", "")
        parsed_json = extract_json_object(llm_response)

        return response.status_code, elapsed_ms, parsed_json, llm_response

    def validate_one_recommendation(self, reco: dict[str, Any]) -> ValidationResult:
        product_id = str(reco.get("product_id") or "").strip() or None
        weburl = str(reco.get("weburl") or "").strip() or None
        normalized_url = normalize_weburl(weburl)

        exists_by_id = bool(product_id and product_id in self.id_to_product)
        exists_by_url = bool(normalized_url and normalized_url in self.url_to_products)

        id_url_same_product = False
        if exists_by_id and exists_by_url and product_id and normalized_url:
            by_id = self.id_to_product.get(product_id)
            same = any(str(item.get("_id")) == str(by_id.get("_id")) for item in self.url_to_products[normalized_url])
            id_url_same_product = bool(same)
        elif exists_by_id and not weburl:
            id_url_same_product = True
        elif exists_by_url and not product_id:
            id_url_same_product = True

        is_valid = False
        reason = ""

        if exists_by_id and exists_by_url:
            if id_url_same_product:
                is_valid = True
                reason = "id+url both exist and match same product"
            else:
                reason = "id and url exist but point to different products"
        elif exists_by_id and not weburl:
            is_valid = True
            reason = "id exists in Peko scope (url missing in output)"
        elif exists_by_url and not product_id:
            is_valid = True
            reason = "url exists in Peko scope (id missing in output)"
        elif exists_by_id:
            is_valid = True
            reason = "id exists in Peko scope"
        elif exists_by_url:
            is_valid = True
            reason = "url exists in Peko scope"
        else:
            reason = "neither id nor url found in Peko scope"

        return ValidationResult(
            product_id=product_id,
            weburl=weburl,
            exists_by_id=exists_by_id,
            exists_by_url=exists_by_url,
            id_url_same_product=id_url_same_product,
            is_valid_in_peko_scope=is_valid,
            reason=reason,
        )

    def run_case(self, case: dict[str, str]) -> dict[str, Any]:
        status_code, latency_ms, parsed_json, raw_response = self.call_query_endpoint(case["query"])

        result: dict[str, Any] = {
            "case_id": case["id"],
            "category": case["category"],
            "input_query": case["query"],
            "http_status": status_code,
            "latency_ms": round(latency_ms, 2),
            "json_parsed": parsed_json is not None,
            "recommendations_count": 0,
            "scope_valid_count": 0,
            "scope_invalid_count": 0,
            "case_passed": False,
            "error": None,
            "recommendations": [],
            "raw_response_preview": raw_response[:1200] if raw_response else "",
        }

        if status_code != 200:
            result["error"] = "HTTP error"
            return result

        if parsed_json is None:
            result["error"] = "LLM output is not valid JSON"
            return result

        recos = ensure_list(parsed_json.get("recommendations"))
        result["recommendations_count"] = len(recos)

        if not recos:
            result["error"] = "No recommendations returned"
            return result

        validations: list[dict[str, Any]] = []
        valid_count = 0

        for reco in recos:
            if not isinstance(reco, dict):
                validations.append(
                    {
                        "product_id": None,
                        "weburl": None,
                        "is_valid_in_peko_scope": False,
                        "reason": "Recommendation item is not an object",
                    }
                )
                continue

            validation = self.validate_one_recommendation(reco)
            if validation.is_valid_in_peko_scope:
                valid_count += 1

            validations.append(
                {
                    "product_id": validation.product_id,
                    "weburl": validation.weburl,
                    "product_name": reco.get("product_name"),
                    "reasoning": reco.get("reasoning"),
                    "exists_by_id": validation.exists_by_id,
                    "exists_by_url": validation.exists_by_url,
                    "id_url_same_product": validation.id_url_same_product,
                    "is_valid_in_peko_scope": validation.is_valid_in_peko_scope,
                    "validation_reason": validation.reason,
                }
            )

        invalid_count = len(recos) - valid_count
        result["scope_valid_count"] = valid_count
        result["scope_invalid_count"] = invalid_count
        result["recommendations"] = validations

        result["case_passed"] = invalid_count == 0
        if not result["case_passed"]:
            result["error"] = "One or more recommendations are out of Peko scope"

        return result


def write_reports(summary: dict[str, Any], run_results: list[dict[str, Any]]) -> tuple[str, str]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = os.path.join("tests", "scope")
    os.makedirs(results_dir, exist_ok=True)

    json_path = os.path.join(results_dir, f"scoped_e2e_results_{timestamp}.json")
    with open(json_path, "w", encoding="utf-8") as file:
        json.dump({"summary": summary, "cases": run_results}, file, indent=2, ensure_ascii=False)

    md_path = os.path.join("docs", "Partner_Scoping_Test_Report.md")

    failed_cases = [item for item in run_results if not item.get("case_passed")]
    sample_failures: list[str] = []
    for case in failed_cases[:10]:
        invalid_recos = [r for r in case.get("recommendations", []) if not r.get("is_valid_in_peko_scope")]
        reasons = "; ".join(
            f"id={r.get('product_id')} url={r.get('weburl')} reason={r.get('validation_reason')}"
            for r in invalid_recos[:3]
        )
        sample_failures.append(
            f"- {case['case_id']} ({case['category']}): {case.get('error') or 'Failed'} | {reasons}"
        )

    markdown = [
        "# Partner Scoping E2E Test Report",
        "",
        f"- Generated at: {datetime.now().isoformat(timespec='seconds')}",
        f"- Endpoint: `{summary['base_url']}/query`",
        f"- Partner scope: `{summary['partner_id']}`",
        f"- Total test cases: {summary['total_cases']}",
        f"- Total recommendations validated: {summary['total_recommendations']}",
        f"- In-scope recommendations: {summary['total_valid_recommendations']}",
        f"- Out-of-scope recommendations: {summary['total_invalid_recommendations']}",
        f"- Case pass rate: {summary['case_pass_rate_percent']:.2f}%",
        f"- Recommendation pass rate: {summary['recommendation_pass_rate_percent']:.2f}%",
        f"- Median latency per query: {format_latency(summary['median_latency_ms'])}",
        "",
        "## Conclusion",
        "",
        summary["conclusion"],
        "",
        "## Failed Case Samples",
        "",
    ]

    if sample_failures:
        markdown.extend(sample_failures)
    else:
        markdown.append("- None")

    markdown.extend(
        [
            "",
            "## Artifacts",
            "",
            f"- Full run data: `{json_path}`",
        ]
    )

    with open(md_path, "w", encoding="utf-8") as file:
        file.write("\n".join(markdown) + "\n")

    return json_path, md_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run scoped /query E2E validation against Peko scope")
    parser.add_argument("--base-url", default=os.getenv("LIGHTRAG_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--api-key", default=os.getenv("LIGHTRAG_API_KEY", DEFAULT_API_KEY))
    parser.add_argument("--partner-id", default=DEFAULT_PARTNER_ID)
    parser.add_argument("--mongo-uri", default=os.getenv("MONGO_URI", DEFAULT_MONGO_URI))
    parser.add_argument("--mongo-db", default=DEFAULT_MONGO_DB)
    parser.add_argument("--mongo-collection", default=DEFAULT_MONGO_COLLECTION)
    parser.add_argument("--max-recos", type=int, default=8)
    parser.add_argument("--max-cases", type=int, default=24)
    parser.add_argument("--timeout", type=int, default=120)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cases = build_test_cases()[: max(1, args.max_cases)]

    validator = ScopedE2EValidator(
        base_url=args.base_url,
        api_key=args.api_key,
        partner_id=args.partner_id,
        mongo_uri=args.mongo_uri,
        mongo_db=args.mongo_db,
        mongo_collection=args.mongo_collection,
        max_recos=args.max_recos,
        timeout=args.timeout,
    )

    print("=" * 80)
    print("Scoped Recommendation E2E Validation")
    print("=" * 80)
    print(f"Base URL: {args.base_url}")
    print(f"Partner ID: {args.partner_id}")
    print(f"Mongo DB: {args.mongo_db}.{args.mongo_collection}")
    print(f"Cases: {len(cases)}")
    print("Loading partner product catalog...")

    validator.load_peko_scope_products()
    print(f"Loaded {len(validator.id_to_product)} products from Peko scope")
    print("-" * 80)

    run_results: list[dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        print(f"[{index:02d}/{len(cases):02d}] {case['id']} | {case['category']}")
        result = validator.run_case(case)
        run_results.append(result)

        if result["http_status"] != 200:
            print(f"  ✗ HTTP {result['http_status']}: {result.get('error')}")
            continue

        if not result["json_parsed"]:
            print("  ✗ JSON parse failure")
            continue

        status = "✓" if result["case_passed"] else "✗"
        print(
            f"  {status} recos={result['recommendations_count']} valid={result['scope_valid_count']} "
            f"invalid={result['scope_invalid_count']} latency={format_latency(result['latency_ms'])}"
        )

    total_cases = len(run_results)
    passed_cases = sum(1 for item in run_results if item.get("case_passed"))
    total_recommendations = sum(int(item.get("recommendations_count", 0)) for item in run_results)
    total_valid_recommendations = sum(int(item.get("scope_valid_count", 0)) for item in run_results)
    total_invalid_recommendations = sum(int(item.get("scope_invalid_count", 0)) for item in run_results)
    latencies = [float(item.get("latency_ms", 0)) for item in run_results if item.get("http_status") == 200]
    median_latency_ms = statistics.median(latencies) if latencies else 0.0

    case_pass_rate = (passed_cases / total_cases * 100.0) if total_cases else 0.0
    recommendation_pass_rate = (
        (total_valid_recommendations / total_recommendations * 100.0)
        if total_recommendations
        else 0.0
    )

    conclusion = (
        "✅ Success: Partner scoping is effective for this run. "
        "All returned recommendations were validated against Peko scope."
        if total_invalid_recommendations == 0 and passed_cases == total_cases
        else "⚠️ Partial success: Some recommendations were out of scope or response formatting failed. "
        "Review failed case samples and full JSON artifact."
    )

    summary = {
        "base_url": args.base_url,
        "partner_id": args.partner_id,
        "total_cases": total_cases,
        "passed_cases": passed_cases,
        "total_recommendations": total_recommendations,
        "total_valid_recommendations": total_valid_recommendations,
        "total_invalid_recommendations": total_invalid_recommendations,
        "case_pass_rate_percent": case_pass_rate,
        "recommendation_pass_rate_percent": recommendation_pass_rate,
        "median_latency_ms": median_latency_ms,
        "conclusion": conclusion,
    }

    json_path, md_path = write_reports(summary, run_results)

    print("-" * 80)
    print("Summary")
    print(f"Cases passed: {passed_cases}/{total_cases} ({case_pass_rate:.2f}%)")
    print(
        "Recommendations valid: "
        f"{total_valid_recommendations}/{total_recommendations} ({recommendation_pass_rate:.2f}%)"
    )
    print(f"Median latency: {format_latency(median_latency_ms)}")
    print(conclusion)
    print(f"JSON artifact: {json_path}")
    print(f"Report: {md_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
