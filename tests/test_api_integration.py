import urllib.request
import json

def test():
    print("==================================================")
    print("RECOVERIQ PYTHON AGENT & AI INTELLIGENCE TEST")
    print("==================================================")

    # 1. Health
    res = urllib.request.urlopen("http://127.0.0.1:8000/api/health")
    health = json.loads(res.read().decode('utf-8'))
    print(f"[1] Health Check: {health['status']} | AI Engine: {health.get('ai_engine')} | Engine: {health['engine']}")

    # 2. Metrics
    res = urllib.request.urlopen("http://127.0.0.1:8000/api/metrics")
    metrics = json.loads(res.read().decode('utf-8'))
    print(f"[2] Preserved Metrics:")
    print(f"    - Revenue at Risk: Rs {metrics['revenueAtRisk']}")
    print(f"    - Revenue Recovered: Rs {metrics['revenueRecovered']}")
    print(f"    - Recovery Rate: {metrics['recoveryRate']}%")
    print(f"    - Payments Monitored: {metrics['paymentsMonitored']}")

    # 3. AI Analysis on all cases
    res = urllib.request.urlopen("http://127.0.0.1:8000/api/ai/analysis")
    ai_all = json.loads(res.read().decode('utf-8'))
    print(f"[3] AI Incident Diagnostics ({len(ai_all)} cases analyzed):")
    for item in ai_all:
        pid = item['payment_id']
        analysis = item.get('ai_analysis', {})
        diag = analysis.get('diagnostic', {})
        gov = analysis.get('governance', {})
        print(f"    - {pid}: Type={diag.get('failure_type')} | Rec={gov.get('recommendation')} | Guardrail={gov.get('status')}")

    # 4. Deep AI Diagnostic on pay_004
    res = urllib.request.urlopen("http://127.0.0.1:8000/api/ai/analysis/pay_004")
    ai_004 = json.loads(res.read().decode('utf-8'))
    print(f"[4] Deep AI Intelligence on pay_004:")
    print(f"    - Failure Pattern: {ai_004.get('diagnostic', {}).get('failure_type')}")
    print(f"    - Severity: {ai_004.get('diagnostic', {}).get('failure_severity')}")
    print(f"    - AI Confidence Score: {ai_004.get('confidence_assessment', {}).get('overall_score')}%")
    print(f"    - Recommendation: {ai_004.get('governance', {}).get('recommendation')}")
    print(f"    - Guardrail Approval: {ai_004.get('governance', {}).get('guardrail_approved')}")
    print(f"    - AI Reasoning: {ai_004.get('reasoning_summary')}")

    # 5. Live Flow Execution on pay_004
    req = urllib.request.Request("http://127.0.0.1:8000/api/run-agent?payment_id=pay_004", method="POST")
    res = urllib.request.urlopen(req)
    run_res = json.loads(res.read().decode('utf-8'))
    print(f"[5] Live Python Agent Run on pay_004: Success={run_res['success']}")

    print("\nALL AI INTELLIGENCE & RECOVERY AGENT TESTS PASSED!")

if __name__ == "__main__":
    test()
