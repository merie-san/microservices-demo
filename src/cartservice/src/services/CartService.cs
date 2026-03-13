using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Diagnostics.Metrics;
using System.Threading.Tasks;
using cartservice.cartstore;
using Grpc.Core;
using Hipstershop;

namespace cartservice.services
{
    public class CartService : Hipstershop.CartService.CartServiceBase
    {
        private readonly ICartStore _cartStore;
        private static readonly Empty Empty = new Empty();

        private static readonly Meter CartMeter = new Meter("cartservice");
        private static readonly Counter<long> requestCounter = CartMeter.CreateCounter<long>("cart_requests_total");
        private static readonly Histogram<double> requestDuration = CartMeter.CreateHistogram<double>("cart_request_duration_seconds");
        private static readonly UpDownCounter<long> activeRequests = CartMeter.CreateUpDownCounter<long>("cart_active_requests");

        public CartService(ICartStore cartStore) => _cartStore = cartStore;

        // Wrapper function
        private async Task<T> TrackMetricsAsync<T>(string functionName, Func<Task<T>> func)
        {
            var start = Stopwatch.GetTimestamp();
            activeRequests.Add(1);
            requestCounter.Add(1, new KeyValuePair<string, object>("function", functionName));

            try
            {
                return await func();
            }
            finally
            {
                var duration = (Stopwatch.GetTimestamp() - start) / (double)Stopwatch.Frequency;
                requestDuration.Record(duration, new KeyValuePair<string, object>("function", functionName));
                activeRequests.Add(-1);
            }
        }

        // Refactored gRPC methods
        public override Task<Empty> AddItem(AddItemRequest request, ServerCallContext context) =>
            TrackMetricsAsync("addItem", () => _cartStore.AddItemAsync(request.UserId, request.Item.ProductId, request.Item.Quantity).ContinueWith(_ => Empty));

        public override Task<Cart> GetCart(GetCartRequest request, ServerCallContext context) =>
            TrackMetricsAsync("getCart", () => _cartStore.GetCartAsync(request.UserId));

        public override Task<Empty> EmptyCart(EmptyCartRequest request, ServerCallContext context) =>
            TrackMetricsAsync("emptyCart", () => _cartStore.EmptyCartAsync(request.UserId).ContinueWith(_ => Empty));
    }
}