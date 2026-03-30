using System.Numerics;
using System.Text.Json;
using System.Text.Json.Serialization;
using Assimp;

namespace MeshComparator;

public class ComparisonReport
{
    [JsonPropertyName("summary")]
    public SummaryData Summary { get; set; } = new();

    [JsonPropertyName("diagnosis")]
    public DiagnosisData Diagnosis { get; set; } = new();

    [JsonPropertyName("boneComparisons")]
    public List<BoneComparisonData> BoneComparisons { get; set; } = new();

    [JsonPropertyName("errors")]
    public List<string> Errors { get; set; } = new();
}

public class SummaryData
{
    [JsonPropertyName("referenceFile")]
    public string ReferenceFile { get; set; } = "";

    [JsonPropertyName("targetFile")]
    public string TargetFile { get; set; } = "";

    [JsonPropertyName("totalBones")]
    public int TotalBones { get; set; }

    [JsonPropertyName("matchingBones")]
    public int MatchingBones { get; set; }

    [JsonPropertyName("issuesFound")]
    public bool IssuesFound { get; set; }

    [JsonPropertyName("criticalIssues")]
    public int CriticalIssues { get; set; }
}

public class DiagnosisData
{
    [JsonPropertyName("inverseBindMatrixIssue")]
    public bool InverseBindMatrixIssue { get; set; }

    [JsonPropertyName("issueType")]
    public string IssueType { get; set; } = "none";

    [JsonPropertyName("confidence")]
    public double Confidence { get; set; }

    [JsonPropertyName("recommendation")]
    public string Recommendation { get; set; } = "";

    [JsonPropertyName("details")]
    public string Details { get; set; } = "";
}

public class BoneComparisonData
{
    [JsonPropertyName("boneName")]
    public string BoneName { get; set; } = "";

    [JsonPropertyName("existsInBoth")]
    public bool ExistsInBoth { get; set; }

    [JsonPropertyName("existsInReference")]
    public bool ExistsInReference { get; set; }

    [JsonPropertyName("existsInTarget")]
    public bool ExistsInTarget { get; set; }

    [JsonPropertyName("hierarchyMatch")]
    public bool HierarchyMatch { get; set; }

    [JsonPropertyName("referenceParent")]
    public string? ReferenceParent { get; set; }

    [JsonPropertyName("targetParent")]
    public string? TargetParent { get; set; }

    [JsonPropertyName("inverseBindMatrix")]
    public MatrixComparisonData? InverseBindMatrix { get; set; }

    [JsonPropertyName("localTransform")]
    public MatrixComparisonData? LocalTransform { get; set; }
}

public class MatrixComparisonData
{
    [JsonPropertyName("match")]
    public bool Match { get; set; }

    [JsonPropertyName("maxError")]
    public float MaxError { get; set; }

    [JsonPropertyName("isTranspose")]
    public bool IsTranspose { get; set; }

    [JsonPropertyName("diagnosis")]
    public string Diagnosis { get; set; } = "";

    [JsonPropertyName("referenceValues")]
    public float[]? ReferenceValues { get; set; }

    [JsonPropertyName("targetValues")]
    public float[]? TargetValues { get; set; }
}

public class MeshComparisonEngine
{
    private const float Epsilon = 0.001f;
    private const float TransposeThreshold = 0.95f; // 95% of bones must be transposes to flag as issue

    public ComparisonReport Compare(string referencePath, string targetPath, bool verbose = false)
    {
        var report = new ComparisonReport();
        report.Summary.ReferenceFile = referencePath;
        report.Summary.TargetFile = targetPath;

        try
        {
            using var context = new AssimpContext();

            // Load scenes without post-processing to preserve original data
            var referenceScene = context.ImportFile(referencePath,
                PostProcessSteps.Triangulate |
                PostProcessSteps.JoinIdenticalVertices);

            var targetScene = context.ImportFile(targetPath,
                PostProcessSteps.Triangulate |
                PostProcessSteps.JoinIdenticalVertices);

            if (verbose)
            {
                Console.WriteLine($"Loaded reference: {referencePath}");
                Console.WriteLine($"  - Meshes: {referenceScene.MeshCount}");
                Console.WriteLine($"  - Materials: {referenceScene.MaterialCount}");
                Console.WriteLine($"");
                Console.WriteLine($"Loaded target: {targetPath}");
                Console.WriteLine($"  - Meshes: {targetScene.MeshCount}");
                Console.WriteLine($"  - Materials: {targetScene.MaterialCount}");
                Console.WriteLine($"");
            }

            // Extract bone data from scenes
            var referenceBones = ExtractBoneData(referenceScene);
            var targetBones = ExtractBoneData(targetScene);

            // Compare bones
            CompareBones(referenceBones, targetBones, report, verbose);

            // Perform diagnosis
            PerformDiagnosis(report, verbose);

            // Update summary
            report.Summary.TotalBones = report.BoneComparisons.Count;
            report.Summary.MatchingBones = report.BoneComparisons.Count(b => b.ExistsInBoth);
            report.Summary.IssuesFound = report.BoneComparisons.Any(b =>
                (b.InverseBindMatrix != null && !b.InverseBindMatrix.Match) ||
                (b.LocalTransform != null && !b.LocalTransform.Match));
            report.Summary.CriticalIssues = report.BoneComparisons.Count(b =>
                b.InverseBindMatrix != null && !b.InverseBindMatrix.Match);
        }
        catch (Exception ex)
        {
            report.Errors.Add($"Failed to compare files: {ex.Message}");
            if (verbose)
            {
                Console.WriteLine($"Error: {ex}");
            }
        }

        return report;
    }

    private Dictionary<string, BoneData> ExtractBoneData(Scene scene)
    {
        var bones = new Dictionary<string, BoneData>();

        // Extract from mesh bones (includes inverse bind matrices)
        foreach (var mesh in scene.Meshes)
        {
            foreach (var bone in mesh.Bones)
            {
                if (!bones.ContainsKey(bone.Name))
                {
                    bones[bone.Name] = new BoneData
                    {
                        Name = bone.Name,
                        InverseBindMatrix = bone.OffsetMatrix,
                        VertexWeights = bone.VertexWeights.ToList()
                    };
                }
            }
        }

        // Extract node hierarchy (includes local transforms)
        ExtractNodeHierarchy(scene.RootNode, null, bones);

        return bones;
    }

    private void ExtractNodeHierarchy(Node node, Node? parent, Dictionary<string, BoneData> bones)
    {
        // Check if this node is a bone
        if (bones.TryGetValue(node.Name, out var boneData))
        {
            boneData.LocalTransform = node.Transform;
            boneData.ParentName = parent?.Name;
        }
        else if (node.Name != "RootNode" && !string.IsNullOrEmpty(node.Name))
        {
            // This is a node in the hierarchy but not a mesh bone
            bones[node.Name] = new BoneData
            {
                Name = node.Name,
                LocalTransform = node.Transform,
                ParentName = parent?.Name
            };
        }

        // Recurse into children
        foreach (var child in node.Children)
        {
            ExtractNodeHierarchy(child, node, bones);
        }
    }

    private void CompareBones(Dictionary<string, BoneData> reference, Dictionary<string, BoneData> target,
        ComparisonReport report, bool verbose)
    {
        var allBoneNames = reference.Keys.Union(target.Keys).ToList();

        foreach (var boneName in allBoneNames)
        {
            var comparison = new BoneComparisonData { BoneName = boneName };

            var refBone = reference.GetValueOrDefault(boneName);
            var targetBone = target.GetValueOrDefault(boneName);

            comparison.ExistsInReference = refBone != null;
            comparison.ExistsInTarget = targetBone != null;
            comparison.ExistsInBoth = refBone != null && targetBone != null;

            if (refBone != null)
            {
                comparison.ReferenceParent = refBone.ParentName;
            }

            if (targetBone != null)
            {
                comparison.TargetParent = targetBone?.ParentName;
            }

            comparison.HierarchyMatch = comparison.ReferenceParent == comparison.TargetParent;

            // Compare inverse bind matrices
            if (refBone?.InverseBindMatrix != null && targetBone?.InverseBindMatrix != null)
            {
                comparison.InverseBindMatrix = CompareMatrices(
                    refBone.InverseBindMatrix!.Value,
                    targetBone.InverseBindMatrix!.Value,
                    verbose);
            }

            // Compare local transforms
            if (refBone?.LocalTransform != null && targetBone?.LocalTransform != null)
            {
                comparison.LocalTransform = CompareMatrices(
                    refBone.LocalTransform!.Value,
                    targetBone.LocalTransform!.Value,
                    verbose && boneName == "root"); // Only verbose for root
            }

            report.BoneComparisons.Add(comparison);
        }
    }

    private MatrixComparisonData CompareMatrices(Matrix4x4 reference, Matrix4x4 target, bool verbose)
    {
        var result = new MatrixComparisonData();

        // Calculate component-wise max error
        float[] errors = new float[16];
        errors[0] = Math.Abs(reference.M11 - target.M11);
        errors[1] = Math.Abs(reference.M12 - target.M12);
        errors[2] = Math.Abs(reference.M13 - target.M13);
        errors[3] = Math.Abs(reference.M14 - target.M14);
        errors[4] = Math.Abs(reference.M21 - target.M21);
        errors[5] = Math.Abs(reference.M22 - target.M22);
        errors[6] = Math.Abs(reference.M23 - target.M23);
        errors[7] = Math.Abs(reference.M24 - target.M24);
        errors[8] = Math.Abs(reference.M31 - target.M31);
        errors[9] = Math.Abs(reference.M32 - target.M32);
        errors[10] = Math.Abs(reference.M33 - target.M33);
        errors[11] = Math.Abs(reference.M34 - target.M34);
        errors[12] = Math.Abs(reference.M41 - target.M41);
        errors[13] = Math.Abs(reference.M42 - target.M42);
        errors[14] = Math.Abs(reference.M43 - target.M43);
        errors[15] = Math.Abs(reference.M44 - target.M44);

        result.MaxError = errors.Max();
        result.Match = result.MaxError < Epsilon;

        // Check if matrices are transposes of each other
        result.IsTranspose = CheckTranspose(reference, target);

        if (result.Match)
        {
            result.Diagnosis = "Exact match";
        }
        else if (result.IsTranspose)
        {
            result.Diagnosis = "Matrices are transposes of each other";
        }
        else
        {
            result.Diagnosis = $"Significant difference (max error: {result.MaxError:F6})";
        }

        // Store values for debugging
        result.ReferenceValues = new[]
        {
            reference.M11, reference.M12, reference.M13, reference.M14,
            reference.M21, reference.M22, reference.M23, reference.M24,
            reference.M31, reference.M32, reference.M33, reference.M34,
            reference.M41, reference.M42, reference.M43, reference.M44
        };

        result.TargetValues = new[]
        {
            target.M11, target.M12, target.M13, target.M14,
            target.M21, target.M22, target.M23, target.M24,
            target.M31, target.M32, target.M33, target.M34,
            target.M41, target.M42, target.M43, target.M44
        };

        return result;
    }

    private bool CheckTranspose(Matrix4x4 a, Matrix4x4 b)
    {
        // Check if b is the transpose of a (within epsilon)
        return ApproxEqual(a.M11, b.M11) &&
               ApproxEqual(a.M22, b.M22) &&
               ApproxEqual(a.M33, b.M33) &&
               ApproxEqual(a.M44, b.M44) &&
               ApproxEqual(a.M12, b.M21) &&
               ApproxEqual(a.M13, b.M31) &&
               ApproxEqual(a.M14, b.M41) &&
               ApproxEqual(a.M21, b.M12) &&
               ApproxEqual(a.M23, b.M32) &&
               ApproxEqual(a.M24, b.M42) &&
               ApproxEqual(a.M31, b.M13) &&
               ApproxEqual(a.M32, b.M23) &&
               ApproxEqual(a.M34, b.M43) &&
               ApproxEqual(a.M41, b.M14) &&
               ApproxEqual(a.M42, b.M24) &&
               ApproxEqual(a.M43, b.M34);
    }

    private bool ApproxEqual(float a, float b)
    {
        return Math.Abs(a - b) < Epsilon;
    }

    private void PerformDiagnosis(ComparisonReport report, bool verbose)
    {
        var diagnosis = report.Diagnosis;

        // Analyze inverse bind matrix issues
        var ibmComparisons = report.BoneComparisons
            .Where(b => b.InverseBindMatrix != null)
            .Select(b => b.InverseBindMatrix!)
            .ToList();

        if (ibmComparisons.Count == 0)
        {
            diagnosis.IssueType = "noData";
            diagnosis.Recommendation = "No inverse bind matrix data found for comparison";
            return;
        }

        int transposeCount = ibmComparisons.Count(m => m.IsTranspose);
        int matchCount = ibmComparisons.Count(m => m.Match);
        int mismatchCount = ibmComparisons.Count(m => !m.Match && !m.IsTranspose);

        double transposeRatio = (double)transposeCount / ibmComparisons.Count;

        if (verbose)
        {
            Console.WriteLine($"Inverse Bind Matrix Analysis:");
            Console.WriteLine($"  - Total: {ibmComparisons.Count}");
            Console.WriteLine($"  - Exact matches: {matchCount}");
            Console.WriteLine($"  - Transpose relationships: {transposeCount} ({transposeRatio:P})");
            Console.WriteLine($"  - Other mismatches: {mismatchCount}");
        }

        // Diagnose based on analysis
        if (matchCount == ibmComparisons.Count)
        {
            diagnosis.InverseBindMatrixIssue = false;
            diagnosis.IssueType = "none";
            diagnosis.Confidence = 1.0;
            diagnosis.Recommendation = "All inverse bind matrices match perfectly";
        }
        else if (transposeRatio >= TransposeThreshold)
        {
            diagnosis.InverseBindMatrixIssue = true;
            diagnosis.IssueType = "transpose";
            diagnosis.Confidence = transposeRatio;
            diagnosis.Recommendation = "GLTF导出中的逆绑定矩阵需要转置。在AssimpMeshExport.cs第376行，确保对GLTF和FBX都使用相同的转置逻辑。";
            diagnosis.Details = $"{transposeCount}/{ibmComparisons.Count} bones have transposed inverse bind matrices";
        }
        else
        {
            diagnosis.InverseBindMatrixIssue = true;
            diagnosis.IssueType = "other";
            diagnosis.Confidence = 0.5;
            diagnosis.Recommendation = "逆绑定矩阵存在不匹配，但不完全是转置问题。需要手动检查具体数值。";
            diagnosis.Details = $"Only {transposeCount}/{ibmComparisons.Count} bones have transpose relationship";
        }
    }
}

public class BoneData
{
    public string Name { get; set; } = "";
    public Matrix4x4? InverseBindMatrix { get; set; }
    public Matrix4x4? LocalTransform { get; set; }
    public string? ParentName { get; set; }
    public List<VertexWeight> VertexWeights { get; set; } = new();
}
