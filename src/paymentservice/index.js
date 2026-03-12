/*
 * Copyright 2018 Google LLC
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

'use strict';

const logger = require('./logger')

if (process.env.DISABLE_PROFILER) {
  logger.info("Profiler disabled.")
} else {
  logger.info("Profiler enabled.")
  require('@google-cloud/profiler').start({
    serviceContext: {
      service: 'paymentservice',
      version: '1.0.0'
    }
  });
}


if (process.env.ENABLE_TRACING == "1") {
  logger.info("Tracing enabled.")

  const { resourceFromAttributes } = require('@opentelemetry/resources');

  const { ATTR_SERVICE_NAME } = require('@opentelemetry/semantic-conventions');

  const { GrpcInstrumentation } = require('@opentelemetry/instrumentation-grpc');
  const { registerInstrumentations } = require('@opentelemetry/instrumentation');
  const opentelemetry = require('@opentelemetry/sdk-node');

  const { ParentBasedSampler, TraceIdRatioBasedSampler } = require('@opentelemetry/sdk-trace-base');
  const { OTLPTraceExporter } = require('@opentelemetry/exporter-otlp-grpc');

  const collectorUrl = process.env.COLLECTOR_SERVICE_ADDR;
  const traceExporter = new OTLPTraceExporter({ url: collectorUrl });

  const sdk = new opentelemetry.NodeSDK({
    resource: resourceFromAttributes({
      [ATTR_SERVICE_NAME]: process.env.OTEL_SERVICE_NAME || 'paymentservice',
    }),
    traceExporter: traceExporter,
    sampler: new ParentBasedSampler({
      root: new TraceIdRatioBasedSampler(0.05),
    }),
  });

  registerInstrumentations({
    instrumentations: [new GrpcInstrumentation()]
  });

  sdk.start()
} else {
  logger.info("Tracing disabled.")
}

let requestCounter;
let requestDuration;
let activeRequests;

if (process.env.ENABLE_METRICS == "1") {
  const { MeterProvider, PeriodicExportingMetricReader } = require('@opentelemetry/sdk-metrics');
  const { OTLPMetricExporter } = require('@opentelemetry/exporter-metrics-otlp-grpc');
  const { resourceFromAttributes } = require('@opentelemetry/resources');
  const { ATTR_SERVICE_NAME } = require('@opentelemetry/semantic-conventions');
  const { metrics } = require('@opentelemetry/api');
  const exporter = new OTLPMetricExporter({
    url: process.env.COLLECTOR_SERVICE_ADDR,
  });

  const reader = new PeriodicExportingMetricReader({
    exporter,
    exportIntervalMillis: 15000,
  });

  const resource = resourceFromAttributes({
    [ATTR_SERVICE_NAME]: process.env.OTEL_SERVICE_NAME,
  });

  const meterProvider = new MeterProvider({
    resource,
    readers: [reader],
  });

  metrics.setGlobalMeterProvider(meterProvider);

  const meter = metrics.getMeter('paymentservice');
  requestCounter = meter.createCounter('payment_requests_total');
  requestDuration = meter.createHistogram('payment_requests_duration', {
    unit: 's',
  });
  activeRequests = meter.createUpDownCounter('payment_active_requests');

}
else {
  logger.info("Metrics disabled.")
}

const path = require('path');
const HipsterShopServer = require('./server');

const PORT = process.env['PORT'];
const PROTO_PATH = path.join(__dirname, '/proto/');

const server = new HipsterShopServer(PROTO_PATH, requestCounter, requestDuration, activeRequests, PORT);

server.listen();
