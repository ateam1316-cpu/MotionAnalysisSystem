using System.ComponentModel.DataAnnotations;
using Microsoft.AspNetCore.Http;

namespace MotionAnalysis.Web.Models;

public class MovementOption
{
    public string SportType { get; set; } = "";
    public string MovementType { get; set; } = "";
    public string Label { get; set; } = "";
}

public class VideoAnalyzeViewModel
{
    [Display(Name = "影片檔案")]
    public IFormFile? VideoFile { get; set; }

    [Display(Name = "運動類型")]
    public string SportType { get; set; } = "fitness";

    [Display(Name = "動作類型")]
    public string MovementType { get; set; } = "squat";

    [Display(Name = "拍攝角度")]
    public string CameraView { get; set; } = "front";

    [Display(Name = "慣用側")]
    public string DominantSide { get; set; } = "right";

    [Display(Name = "影格間隔")]
    [Range(1, 30)]
    public int FrameInterval { get; set; } = 1;

    [Display(Name = "產生骨架影片")]
    public bool GenerateSkeletonVideo { get; set; } = true;

    [Display(Name = "產生軌跡影片")]
    public bool GenerateTrajectoryVideo { get; set; } = true;

    [Display(Name = "瀏覽器可直接播放（較慢）")]
    public bool BrowserPlayableVideo { get; set; } = false;

    public List<MovementOption> AvailableMovements { get; set; } = new();

    public string? AnalysisJson { get; set; }

    public string? AnalysisId { get; set; }

    public string? SkeletonVideoUrl { get; set; }

    public string? TrajectoryVideoUrl { get; set; }

    public string? RawJsonUrl { get; set; }

    public List<string> WarningMessages { get; set; } = new();

    public string? ErrorMessage { get; set; }

    public static IReadOnlyList<MovementOption> FallbackMovements { get; } =
    [
        new() { SportType = "fitness", MovementType = "squat", Label = "健身／深蹲" },
        new() { SportType = "badminton", MovementType = "smash", Label = "羽球／殺球" },
        new() { SportType = "baseball", MovementType = "pitch", Label = "棒球／投球" },
    ];

    public static IReadOnlyList<(string Value, string Label)> CameraViews { get; } =
    [
        ("front", "正面"),
        ("rear", "後方"),
        ("side_left", "左側"),
        ("side_right", "右側"),
        ("front_diagonal_left", "左前斜"),
        ("front_diagonal_right", "右前斜"),
        ("rear_diagonal_left", "左後斜"),
        ("rear_diagonal_right", "右後斜"),
        ("unknown", "未知"),
    ];
}
