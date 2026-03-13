#! /usr/bin/bash
# Requires kubectl,kind and skaffold installed on the system, run this script on the root directoryof the project
set -e pipefail
if kind get clusters | grep -q "kind"; then
    echo "Kind cluster already exists, skipping creation"
else
    envsubst < kind-config.yaml.template > kind-config.yaml
    kind create cluster --config kind-config.yaml
fi
cd kustomize || exit
kubectl apply -k .
cd .. || exit
skaffold run 
sleep 3
kubectl get pods


