using System.Net.Http.Headers;
using Microsoft.AspNetCore.Http;

namespace MotionAnalysis.Web.Services;

public class PoseApiClient
{
    private readonly HttpClient _httpClient;

    public PoseApiClient(HttpClient httpClient)
    {
        _httpClient = httpClient;
    }

    public async Task<string> AnalyzeVideoAsync(IFormFile videoFile)
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

        var response = await _httpClient.PostAsync("/analyze/video", form);

        var responseText = await response.Content.ReadAsStringAsync();

        if (!response.IsSuccessStatusCode)
        {
            throw new Exception($"Pose API error: {response.StatusCode}, {responseText}");
        }

        return responseText;
    }
}
