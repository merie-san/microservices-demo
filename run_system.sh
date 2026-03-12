#! /usr/bin/bash
# Requires kubectl,kind and skaffold installed on the system, run this script on the root directoryof the project
set -e pipefail

envsubst < kind-config.yaml.template > kind-config.yaml
kind create cluster --config kind-config.yaml
cd kustomize || exit
kubectl apply -k .
cd .. || exit
skaffold run 
kubectl get pods


