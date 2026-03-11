// Copyright 2023 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package main

import (
	"context"
	"strings"
	"time"

	pb "github.com/GoogleCloudPlatform/microservices-demo/src/productcatalogservice/genproto"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/metric"
	"google.golang.org/grpc/codes"
	healthpb "google.golang.org/grpc/health/grpc_health_v1"
	"google.golang.org/grpc/status"
)

type productCatalog struct {
	pb.UnimplementedProductCatalogServiceServer
	catalog         pb.ListProductsResponse
	requestCounter  metric.Int64Counter
	requestDuration metric.Float64Histogram
	activeRequests  metric.Int64UpDownCounter
}

func (p *productCatalog) Check(ctx context.Context, req *healthpb.HealthCheckRequest) (*healthpb.HealthCheckResponse, error) {
	return &healthpb.HealthCheckResponse{Status: healthpb.HealthCheckResponse_SERVING}, nil
}

func (p *productCatalog) Watch(req *healthpb.HealthCheckRequest, ws healthpb.Health_WatchServer) error {
	return status.Errorf(codes.Unimplemented, "health check via Watch not implemented")
}

func (p *productCatalog) handleMetrics(ctx context.Context, functionName string, f func() error) error {
	start := time.Now()

	labels := []attribute.KeyValue{
		attribute.String("function", functionName),
	}

	p.requestCounter.Add(ctx, 1, metric.WithAttributes(labels...))
	p.activeRequests.Add(ctx, 1, metric.WithAttributes(labels...))

	defer func() {
		duration := time.Since(start).Seconds()
		p.requestDuration.Record(ctx, duration, metric.WithAttributes(labels...))
		p.activeRequests.Add(ctx, -1, metric.WithAttributes(labels...))
	}()

	return f()
}

func (p *productCatalog) ListProducts(ctx context.Context, req *pb.Empty) (*pb.ListProductsResponse, error) {
	var resp *pb.ListProductsResponse
	err := p.handleMetrics(ctx, "listProducts", func() error {
		var err error
		resp, err = p.listProductsLogic()
		return err
	})
	return resp, err
}

func (p *productCatalog) listProductsLogic() (*pb.ListProductsResponse, error) {
	time.Sleep(extraLatency)

	return &pb.ListProductsResponse{Products: p.parseCatalog()}, nil
}

func (p *productCatalog) GetProduct(ctx context.Context, req *pb.GetProductRequest) (*pb.Product, error) {
	var resp *pb.Product
	err := p.handleMetrics(ctx, "getProduct", func() error {
		var err error
		resp, err = p.getProductLogic(req)
		return err
	})
	return resp, err
}

func (p *productCatalog) getProductLogic(req *pb.GetProductRequest) (*pb.Product, error) {
	time.Sleep(extraLatency)

	var found *pb.Product
	for i := 0; i < len(p.parseCatalog()); i++ {
		if req.Id == p.parseCatalog()[i].Id {
			found = p.parseCatalog()[i]
		}
	}

	if found == nil {
		return nil, status.Errorf(codes.NotFound, "no product with ID %s", req.Id)
	}
	return found, nil
}

func (p *productCatalog) SearchProducts(ctx context.Context, req *pb.SearchProductsRequest) (*pb.SearchProductsResponse, error) {
	var resp *pb.SearchProductsResponse
	err := p.handleMetrics(ctx, "searchProducts", func() error {
		var err error
		resp, err = p.searchProductsLogic(req)
		return err
	})
	return resp, err
}

func (p *productCatalog) searchProductsLogic(req *pb.SearchProductsRequest) (*pb.SearchProductsResponse, error) {
	time.Sleep(extraLatency)

	var ps []*pb.Product
	for _, product := range p.parseCatalog() {
		if strings.Contains(strings.ToLower(product.Name), strings.ToLower(req.Query)) ||
			strings.Contains(strings.ToLower(product.Description), strings.ToLower(req.Query)) {
			ps = append(ps, product)
		}
	}

	return &pb.SearchProductsResponse{Results: ps}, nil
}

func (p *productCatalog) parseCatalog() []*pb.Product {
	if reloadCatalog || len(p.catalog.Products) == 0 {
		err := loadCatalog(&p.catalog)
		if err != nil {
			return []*pb.Product{}
		}
	}

	return p.catalog.Products
}
