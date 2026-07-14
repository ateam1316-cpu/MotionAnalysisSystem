using Microsoft.AspNetCore.Http;

namespace MotionAnalysis.Web.Models;

public class VideoAnalyzeViewModel
{
    public IFormFile? VideoFile { get; set; }

    public string? AnalysisJson { get; set; }

    public string? ErrorMessage { get; set; }
}
