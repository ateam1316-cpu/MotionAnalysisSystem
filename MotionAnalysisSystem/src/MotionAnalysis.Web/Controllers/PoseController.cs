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
    public async Task<IActionResult> Index()
    {
        var model = new VideoAnalyzeViewModel();
        await FillMovementsAsync(model);
        return View(model);
    }

    [HttpPost]
    [RequestSizeLimit(524_288_000)]
    public async Task<IActionResult> Index(VideoAnalyzeViewModel model)
    {
        await FillMovementsAsync(model);

        if (model.VideoFile == null || model.VideoFile.Length == 0)
        {
            model.ErrorMessage = "請上傳影片檔案。";
            return View(model);
        }

        if (string.IsNullOrWhiteSpace(model.SportType) || string.IsNullOrWhiteSpace(model.MovementType))
        {
            model.ErrorMessage = "請選擇運動類型與動作類型。";
            return View(model);
        }

        if (model.FrameInterval < 1)
        {
            model.FrameInterval = 1;
        }

        try
        {
            var resultJson = await _poseApiClient.AnalyzeVideoAsync(
                model.VideoFile,
                model.SportType.Trim().ToLowerInvariant(),
                model.MovementType.Trim().ToLowerInvariant(),
                string.IsNullOrWhiteSpace(model.CameraView) ? "unknown" : model.CameraView.Trim().ToLowerInvariant(),
                string.IsNullOrWhiteSpace(model.DominantSide) ? "right" : model.DominantSide.Trim().ToLowerInvariant(),
                model.FrameInterval,
                model.GenerateSkeletonVideo,
                model.GenerateTrajectoryVideo,
                model.BrowserPlayableVideo,
                model.CompareWithFull);

            PoseApiClient.PopulateResultFields(model, resultJson);
        }
        catch (Exception ex)
        {
            model.ErrorMessage = ex.Message;
        }

        return View(model);
    }

    /// <summary>
    /// Continue Full-model analysis after Lite results are already shown.
    /// </summary>
    [HttpPost]
    public async Task<IActionResult> CompareFull([FromForm] string analysisId)
    {
        if (string.IsNullOrWhiteSpace(analysisId))
        {
            return BadRequest(new { success = false, message = "缺少 analysisId。" });
        }

        try
        {
            var resultJson = await _poseApiClient.CompareFullAsync(analysisId.Trim());
            return Content(resultJson, "application/json");
        }
        catch (Exception ex)
        {
            return StatusCode(500, new { success = false, message = ex.Message });
        }
    }

    private async Task FillMovementsAsync(VideoAnalyzeViewModel model)
    {
        var movements = await _poseApiClient.GetSupportedMovementsAsync();
        model.AvailableMovements = movements.ToList();
    }
}
