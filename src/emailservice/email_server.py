#!/usr/bin/python
#
# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from concurrent import futures
import argparse
import os
import sys
import time
import grpc
import traceback
from jinja2 import Environment, FileSystemLoader, select_autoescape, TemplateError
from google.api_core.exceptions import GoogleAPICallError
from google.auth.exceptions import DefaultCredentialsError

import demo_pb2
import demo_pb2_grpc
from grpc_health.v1 import health_pb2
from grpc_health.v1 import health_pb2_grpc

from opentelemetry import trace
from opentelemetry.instrumentation.grpc import GrpcInstrumentorServer
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.attributes import service_attributes
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    PeriodicExportingMetricReader,
)


# @TODO: Temporarily removed in https://github.com/GoogleCloudPlatform/microservices-demo/pull/3196
# import googlecloudprofiler

from logger import getJSONLogger

logger = getJSONLogger("emailservice-server")

# Loads confirmation email template from file
env = Environment(
    loader=FileSystemLoader("templates"), autoescape=select_autoescape(["html", "xml"])
)
template = env.get_template("confirmation.html")


class BaseEmailService(demo_pb2_grpc.EmailServiceServicer):
    def Check(self, request, context):
        return health_pb2.HealthCheckResponse(
            status=health_pb2.HealthCheckResponse.SERVING
        )

    def Watch(self, request, context):
        return health_pb2.HealthCheckResponse(
            status=health_pb2.HealthCheckResponse.UNIMPLEMENTED
        )


class EmailService(BaseEmailService):
    def __init__(self):
        raise Exception("cloud mail client not implemented")
        super().__init__()

    @staticmethod
    def send_email(client, email_address, content):
        response = client.send_message(
            sender=client.sender_path(project_id, region, sender_id),
            envelope_from_authority="",
            header_from_authority="",
            envelope_from_address=from_address,
            simple_message={
                "from": {
                    "address_spec": from_address,
                },
                "to": [{"address_spec": email_address}],
                "subject": "Your Confirmation Email",
                "html_body": content,
            },
        )
        logger.info("Message sent: {}".format(response.rfc822_message_id))

    def SendOrderConfirmation(self, request, context):
        email = request.email
        order = request.order

        try:
            confirmation = template.render(order=order)
        except TemplateError as err:
            context.set_details(
                "An error occurred when preparing the confirmation mail."
            )
            logger.error(err.message)
            context.set_code(grpc.StatusCode.INTERNAL)
            return demo_pb2.Empty()

        try:
            EmailService.send_email(self.client, email, confirmation)
        except GoogleAPICallError as err:
            context.set_details("An error occurred when sending the email.")
            print(err.message)
            context.set_code(grpc.StatusCode.INTERNAL)
            return demo_pb2.Empty()

        return demo_pb2.Empty()


class DummyEmailService(BaseEmailService):

    def __init__(self, request_counter, request_duration, active_requests):
        super().__init__()
        self.request_counter = request_counter
        self.request_duration = request_duration
        self.active_requests = active_requests

    def SendOrderConfirmation(self, request, context):
        start=time.time()
        labels = {"function": "sendOrderConfirmation"}
        if self.request_counter:
            self.request_counter.add(1, labels)
        if self.active_requests:
            self.active_requests.add(1, labels)
        res = self.send_order_confirmation_logic(request)
        duration=time.time() - start
        if self.request_duration:
            self.request_duration.record(duration, labels)
        if self.active_requests:
            self.active_requests.add(-1, labels)
        return res

    def send_order_confirmation_logic(self, request):
        logger.info(
            "A request to send order confirmation email to {} has been received.".format(
                request.email
            )
        )
        return demo_pb2.Empty()


class HealthCheck:
    def Check(self, request, context):
        return health_pb2.HealthCheckResponse(
            status=health_pb2.HealthCheckResponse.SERVING
        )


def start(dummy_mode, request_counter, request_duration, active_requests):
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=10),
    )
    service = None
    if dummy_mode:
        service = DummyEmailService(request_counter, request_duration, active_requests)
    else:
        raise Exception("non-dummy mode not implemented yet")

    demo_pb2_grpc.add_EmailServiceServicer_to_server(service, server)
    health_pb2_grpc.add_HealthServicer_to_server(service, server)

    port = os.environ.get("PORT", "8080")
    logger.info("listening on port: " + port)
    server.add_insecure_port("[::]:" + port)
    server.start()
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        server.stop(0)


def initStackdriverProfiling():
    project_id = None
    try:
        project_id = os.environ["GCP_PROJECT_ID"]
    except KeyError:
        # Environment variable not set
        pass

    # @TODO: Temporarily removed in https://github.com/GoogleCloudPlatform/microservices-demo/pull/3196
    # for retry in range(1,4):
    #   try:
    #     if project_id:
    #       googlecloudprofiler.start(service='email_server', service_version='1.0.0', verbose=0, project_id=project_id)
    #     else:
    #       googlecloudprofiler.start(service='email_server', service_version='1.0.0', verbose=0)
    #     logger.info("Successfully started Stackdriver Profiler.")
    #     return
    #   except (BaseException) as exc:
    #     logger.info("Unable to start Stackdriver Profiler Python agent. " + str(exc))
    #     if (retry < 4):
    #       logger.info("Sleeping %d to retry initializing Stackdriver Profiler"%(retry*10))
    #       time.sleep (1)
    #     else:
    #       logger.warning("Could not initialize Stackdriver Profiler after retrying, giving up")
    return


if __name__ == "__main__":
    logger.info("starting the email service in dummy mode.")

    # Profiler
    try:
        if "DISABLE_PROFILER" in os.environ:
            raise KeyError()
        else:
            logger.info("Profiler enabled.")
            initStackdriverProfiling()
    except KeyError:
        logger.info("Profiler disabled.")

    # Tracing
    try:
        if os.environ["ENABLE_TRACING"] == "1":
            otel_endpoint = os.getenv("COLLECTOR_SERVICE_ADDR", "localhost:4317")
            trace.set_tracer_provider(TracerProvider(ParentBased(TraceIdRatioBased(0.05))))
            trace.get_tracer_provider().add_span_processor(
                BatchSpanProcessor(
                    OTLPSpanExporter(endpoint=otel_endpoint, insecure=True)
                )
            )
        grpc_server_instrumentor = GrpcInstrumentorServer()
        grpc_server_instrumentor.instrument()

    except (KeyError, DefaultCredentialsError):
        logger.info("Tracing disabled.")
    except Exception as e:
        logger.warn(
            f"Exception on Cloud Trace setup: {traceback.format_exc()}, tracing disabled."
        )
    request_counter = None
    request_duration = None
    active_requests = None
    # Metrics
    try:
        if os.environ["ENABLE_METRICS"] == "1":
            otel_endpoint = os.getenv("COLLECTOR_SERVICE_ADDR", "localhost:4317")
            exporter = OTLPMetricExporter(endpoint=otel_endpoint, insecure=True)
            reader = PeriodicExportingMetricReader(
                exporter, export_interval_millis=15000
            )

            resource = Resource.merge(
                Resource.create({}),
                Resource.create(
                    {service_attributes.SERVICE_NAME: os.environ["OTEL_SERVICE_NAME"]}
                ),
            )

            provider = MeterProvider(resource=resource, metric_readers=[reader])
            metrics.set_meter_provider(provider)
            meter = metrics.get_meter("emailservice")

            request_counter = meter.create_counter("email_requests_total")

            request_duration = meter.create_histogram(
                "email_request_duration", unit="s"
            )

            active_requests = meter.create_up_down_counter("email_active_requests")

    except KeyError:
        logger.info("Metrics disabled.")
    except Exception as e:
        logger.fatal(
            f"Exception on Metrics setup: {traceback.format_exc()}, metrics disabled."
        )

    start(True, request_counter, request_duration, active_requests)
