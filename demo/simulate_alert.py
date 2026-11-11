import sys
import time
from assistant.models import AlertPayload
from assistant.handler import send_alert_to_discord

SCENARIOS = {
    "1": AlertPayload(
        alert_name="KubePodCrashLooping",
        severity="critical",
        service="auth-service",
        namespace="production",
        summary="Pod auth-service-7f89d986b-kx2lp crashing repeatedly. Exit Code: 1 (Application Error).",
        ai_recommendation="kubectl logs -n production auth-service-7f89d986b-kx2lp --previous --tail=50\nkubectl describe pod -n production auth-service-7f89d986b-kx2lp | grep -A 5 State"
    ),
    "2": AlertPayload(
        alert_name="NodeMemoryPressure",
        severity="warning",
        service="worker-node-03",
        namespace="kube-system",
        summary="Node worker-node-03 memory utilization exceeded 91%. Risk of Pod evictions.",
        ai_recommendation="kubectl top nodes\nkubectl get pods -A --sort-by='.status.containerStatuses[0].restartCount'"
    ),
    "3": AlertPayload(
        alert_name="Ingress5xxRateHigh",
        severity="critical",
        service="nginx-ingress-controller",
        namespace="ingress-nginx",
        summary="HTTP 502/504 Bad Gateway responses spiked to 14.8% over the last 5 minutes.",
        ai_recommendation="kubectl logs -n ingress-nginx -l app.kubernetes.io/name=ingress-nginx --tail=100 | grep '502\\|504'"
    )
}

def main():
    print("=" * 50)
    print("  🚨 AIOps On-Call Assistant - Incident Simulator")
    print("=" * 50)
    print("Select a production incident scenario to simulate:")
    print("1) Pod CrashLoopBackOff (Auth Service)")
    print("2) Node Memory Pressure (Worker Node 03)")
    print("3) High HTTP 5xx Error Rate (Nginx Ingress)")
    print("4) Trigger All Scenarios (Batch Incident Simulation)")
    print("=" * 50)

    choice = input("Enter choice [1-4]: ").strip()

    if choice in SCENARIOS:
        print(f"\n[+] Dispatching {SCENARIOS[choice].alert_name} alert to Discord...")
        send_alert_to_discord(SCENARIOS[choice])
        print("[✓] Alert delivered successfully!")
    elif choice == "4":
        print("\n[+] Triggering batch incident alerts...")
        for key, scenario in SCENARIOS.items():
            print(f" -> Sending: {scenario.alert_name}")
            send_alert_to_discord(scenario)
            time.sleep(1.5)  # Discord API rate-limiting compliance
        print("[✓] All alerts dispatched successfully!")
    else:
        print("[-] Invalid choice. Exiting.")
        sys.exit(1)

if __name__ == "__main__":
    main()
