using Microsoft.AspNetCore.Mvc;
using MotionAnalysis.Web.Models;
using MotionAnalysis.Web.Services;

namespace MotionAnalysis.Web.Controllers;

public class PoseController : Controller
{
    private readonly PoseApiClient _poseApiClient;

    public PoseController(PoseApiClient poseApiClient)
    {
        _poseApiClient = poseApiClient;
    }

    [HttpGet]
    public IActionResult Index()
    {
        return View(new VideoAnalyzeViewModel());
    }

    [HttpPost]
    public async Task<IActionResult> Index(VideoAnalyzeViewModel model)
    {
        if (model.VideoFile == null || model.VideoFile.Length == 0)
        {
            model.ErrorMessage = "請上傳影片檔案。";
            return View(model);
        }

        try
        {
            var resultJson = await _poseApiClient.AnalyzeVideoAsync(model.VideoFile);
            model.AnalysisJson = resultJson;
        }
        catch (Exception ex)
        {
            model.ErrorMessage = ex.Message;
        }

        return View(model);
    }
}
