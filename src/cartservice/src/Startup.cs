using System;
using Microsoft.AspNetCore.Builder;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using cartservice.cartstore;
using cartservice.services;
using OpenTelemetry.Trace;
using OpenTelemetry.Metrics;
using OpenTelemetry.Resources;
using OpenTelemetry.Exporter;

namespace cartservice
{
    public class Startup
    {
        private static readonly string ServiceName = Environment.GetEnvironmentVariable("OTEL_SERVICE_NAME") ?? "cartservice";
        private static readonly string CollectorServiceAddr = Environment.GetEnvironmentVariable("COLLECTOR_SERVICE_ADDR") ?? "http://opentelemetrycollector:4317";

        public Startup(IConfiguration configuration) => Configuration = configuration;
        public IConfiguration Configuration { get; }

        public void ConfigureServices(IServiceCollection services)
        {
            string redisAddress = Configuration["REDIS_ADDR"];
            string spannerProjectId = Configuration["SPANNER_PROJECT"];
            string spannerConnectionString = Configuration["SPANNER_CONNECTION_STRING"];
            string alloyDBConnectionString = Configuration["ALLOYDB_PRIMARY_IP"];

            if (!string.IsNullOrEmpty(redisAddress))
            {
                services.AddStackExchangeRedisCache(options => options.Configuration = redisAddress);
                services.AddSingleton<ICartStore, RedisCartStore>();
            }
            else if (!string.IsNullOrEmpty(spannerProjectId) || !string.IsNullOrEmpty(spannerConnectionString))
            {
                services.AddSingleton<ICartStore, SpannerCartStore>();
            }
            else if (!string.IsNullOrEmpty(alloyDBConnectionString))
            {
                Console.WriteLine("Creating AlloyDB cart store");
                services.AddSingleton<ICartStore, AlloyDBCartStore>();
            }
            else
            {
                Console.WriteLine("Using in-memory store");
                services.AddDistributedMemoryCache();
                services.AddSingleton<ICartStore, RedisCartStore>();
            }

            services.AddGrpc();

            // Modern OpenTelemetry API (1.x+): single AddOpenTelemetry() call
            var otelBuilder = services.AddOpenTelemetry()
                .ConfigureResource(r => r.AddService(ServiceName));

            if (Environment.GetEnvironmentVariable("ENABLE_TRACING") == "1")
            {
                otelBuilder.WithTracing(builder =>
                {
                    builder
                        .AddAspNetCoreInstrumentation()
                        .SetSampler(new ParentBasedSampler(new TraceIdRatioBasedSampler(0.05)))
                        .AddOtlpExporter(opt => opt.Endpoint = new Uri(CollectorServiceAddr));
                });

                Console.WriteLine("Tracing enabled with ParentBased(TraceIdRatio=0.05)");
            }

            if (Environment.GetEnvironmentVariable("ENABLE_METRICS") == "1")
            {
                otelBuilder.WithMetrics(builder =>
                {
                    builder
                        .AddAspNetCoreInstrumentation()
                        .AddMeter(ServiceName)
                        .AddOtlpExporter((exporterOptions, readerOptions) =>
                        {
                            exporterOptions.Endpoint = new Uri(CollectorServiceAddr);
                            readerOptions.PeriodicExportingMetricReaderOptions.ExportIntervalMilliseconds = 15000;
                        });
                });

                Console.WriteLine("Metrics collection enabled with 15s export interval.");
            }
        }

        public void Configure(IApplicationBuilder app, IWebHostEnvironment env)
        {
            if (env.IsDevelopment()) app.UseDeveloperExceptionPage();

            app.UseRouting();

            app.UseEndpoints(endpoints =>
            {
                endpoints.MapGrpcService<CartService>();
                endpoints.MapGrpcService<HealthCheckService>();
                endpoints.MapGet("/", async context =>
                {
                    await context.Response.WriteAsync(
                        "Communication with gRPC endpoints must be made through a gRPC client.");
                });
            });
        }
    }
}