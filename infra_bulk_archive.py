import requests
import time

url_template = "https://demo.digiicampus.com/api/infrastructureVersion/archive?archive=true&infrastructureVersionId={}"

headers = {
    'Content-Type': 'application/json',
    'Auth-Token': ''  # Replace with your actual token
}

# Add all 602 infrastructure version IDs here
infra_ids = [917, 918, 919, 920, 921, 922, 923, 924]


success_count = 0
failure_count = 0

for i, infra_id in enumerate(infra_ids, 1):
    url = url_template.format(infra_id)
    
    try:
        response = requests.put(url, headers=headers, data={}, timeout=30, verify=False)
        
        if response.status_code == 200:
            success_count += 1
            print(f"[{i}/{len(infra_ids)}] ✓ Archived infra ID: {infra_id}")
        else:
            failure_count += 1
            print(f"[{i}/{len(infra_ids)}] ✗ Failed infra ID: {infra_id} | Status: {response.status_code} | Response: {response.text}")
    
    except Exception as e:
        failure_count += 1
        print(f"[{i}/{len(infra_ids)}] ✗ Error for infra ID: {infra_id} | {str(e)}")
    
    # 5 second delay between requests
    if i < len(infra_ids):
        time.sleep(5)

print(f"\n--- Done ---")
print(f"Total: {len(infra_ids)} | Success: {success_count} | Failed: {failure_count}")
