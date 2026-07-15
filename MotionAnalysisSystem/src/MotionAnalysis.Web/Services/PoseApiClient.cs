using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using Microsoft.AspNetCore.Http;
using MotionAnalysis.Web.Models;

namespace MotionAnalysis.Web.Services;

public class PoseApiClient
{
    private readonly HttpClient _httpClient;

    public PoseApiClient(HttpClient httpClient)
    {
        _httpClient = httpClient;
    }

    public async Task<IReadOnlyList<MovementOption>> GetSupportedMovementsAsync()
    {
        try
        {
            var response = await _httpClient.GetAsync("/movements");
            var responseText = await response.Content.ReadAsStringAsync();
            if (!response.IsSuccessStatusCode)
            {
                return VideoAnalyzeViewModel.FallbackMovements;
            }

            using var doc = JsonDocument.Parse(responseText);
            if (!doc.RootElement.TryGetProperty("movements", out var arr)
                || arr.ValueKind != JsonValueKind.Array)
            {
                return VideoAnalyzeViewModel.FallbackMovements;
            }

            var list = new List<MovementOption>();
            foreach (var item in arr.EnumerateArray())
            {
                var sport = item.TryGetProperty("sportType", out var s) ? s.GetString() : null;
                var movement = item.TryGetProperty("movementType", out var m) ? m.GetString() : null;
                var label = item.TryGetProperty("label", out var l) ? l.GetString() : null;
                if (string.IsNullOrWhiteSpace(sport) || string.IsNullOrWhiteSpace(movement))
                {
                    continue;
                }

                list.Add(new MovementOption
                {
                    SportType = sport!,
                    MovementType = movement!,
                    Label = string.IsNullOrWhiteSpace(label) ? $"{sport}/{movement}" : label!,
                });
            }

            return list.Count > 0 ? list : VideoAnalyzeViewModel.FallbackMovements;
        }
        catch
        {
            return VideoAnalyzeViewModel.FallbackMovements;
        }
    }

    public async Task<string> AnalyzeVideoAsync(
        IFormFile videoFile,
        string sportType,
        string movementType,
        string cameraView,
        string dominantSide,
        int frameInterval,
        bool generateSkeletonVideo,
        bool generateTrajectoryVideo,
        bool browserPlayableVideo)
    {
        using var form = new MultipartFormDataContent();

        await using var stream = videoFile.OpenReadStream();

        var fileContent = new StreamContent(stream);
        fileContent.Headers.ContentType = new MediaTypeHeaderValue(
            string.IsNullOrWhiteSpace(videoFile.ContentType)
                ? "application/octet-stream"
                : videoFile.ContentType
        );

        form.Add(fileContent, "file", videoFile.FileName);
        form.Add(new StringContent(sportType, Encoding.UTF8), "sportType");
        form.Add(new StringContent(movementType, Encoding.UTF8), "movementType");
        form.Add(new StringContent(cameraView, Encoding.UTF8), "cameraView");
        form.Add(new StringContent(dominantSide, Encoding.UTF8), "dominantSide");
        form.Add(new StringContent(frameInterval.ToString(), Encoding.UTF8), "frameInterval");
        form.Add(new StringContent(generateSkeletonVideo ? "true" : "false", Encoding.UTF8), "generateSkeletonVideo");
        form.Add(new StringContent(generateTrajectoryVideo ? "true" : "false", Encoding.UTF8), "generateTrajectoryVideo");
        form.Add(new StringContent(browserPlayableVideo ? "true" : "false", Encoding.UTF8), "browserPlayableVideo");

        var response = await _httpClient.PostAsync("/analyze/video", form);
        var responseText = await response.Content.ReadAsStringAsync();

        if (!response.IsSuccessStatusCode)
        {
            throw new Exception($"Pose API error: {response.StatusCode}, {responseText}");
        }

        return responseText;
    }

    public static void PopulateResultFields(VideoAnalyzeViewModel model, string resultJson)
    {
        model.AnalysisJson = resultJson;
        model.WarningMessages.Clear();
        model.AnalysisId = null;
        model.SkeletonVideoUrl = null;
        model.TrajectoryVideoUrl = null;
        model.RawJsonUrl = null;

        try
        {
            using var doc = JsonDocument.Parse(resultJson);
            var root = doc.RootElement;

            if (root.TryGetProperty("analysisId", out var idProp))
            {
                model.AnalysisId = idProp.GetString();
            }

            if (root.TryGetProperty("outputFiles", out var files) && files.ValueKind == JsonValueKind.Object)
            {
                if (files.TryGetProperty("skeletonVideoUrl", out var sk) && sk.ValueKind == JsonValueKind.String)
                {
                    model.SkeletonVideoUrl = sk.GetString();
                }

                if (files.TryGetProperty("trajectoryVideoUrl", out var tr) && tr.ValueKind == JsonValueKind.String)
                {
                    model.TrajectoryVideoUrl = tr.GetString();
                }

                if (files.TryGetProperty("rawJsonUrl", out var raw) && raw.ValueKind == JsonValueKind.String)
                {
                    model.RawJsonUrl = raw.GetString();
                }
            }

            if (root.TryGetProperty("warnings", out var warnings) && warnings.ValueKind == JsonValueKind.Array)
            {
                foreach (var w in warnings.EnumerateArray())
                {
                    if (w.TryGetProperty("message", out var msg) && msg.ValueKind == JsonValueKind.String)
                    {
                        var text = msg.GetString();
                        if (!string.IsNullOrWhiteSpace(text))
                        {
                            model.WarningMessages.Add(text!);
                        }
                    }
                }
            }

            if (root.TryGetProperty("success", out var successProp)
                && successProp.ValueKind == JsonValueKind.False)
            {
                if (root.TryGetProperty("message", out var err) && err.ValueKind == JsonValueKind.String)
                {
                    model.ErrorMessage = err.GetString();
                }
            }
        }
        catch (JsonException)
        {
            // Keep raw JSON only when parse fails.
        }
    }
}
