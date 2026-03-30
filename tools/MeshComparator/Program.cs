using System.CommandLine;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace MeshComparator;

class Program
{
    static async Task<int> Main(string[] args)
    {
        var rootCommand = new RootCommand("FBX/GLTF Mesh Comparison Tool - Automated diagnosis for skinning issues");

        var referenceOption = new Option<string>(
            name: "--reference",
            description: "Path to reference FBX file (correct skinning)") { IsRequired = true };

        var targetOption = new Option<string>(
            name: "--target",
            description: "Path to target GLTF/FBX file to compare") { IsRequired = true };

        var outputOption = new Option<string?>(
            name: "--output",
            description: "Output JSON report file path (optional, outputs to stdout if not specified)");

        var verboseOption = new Option<bool>(
            name: "--verbose",
            description: "Enable verbose output",
            getDefaultValue: () => false);

        var formatOption = new Option<string>(
            name: "--format",
            description: "Output format: json or summary",
            getDefaultValue: () => "json");

        rootCommand.AddOption(referenceOption);
        rootCommand.AddOption(targetOption);
        rootCommand.AddOption(outputOption);
        rootCommand.AddOption(verboseOption);
        rootCommand.AddOption(formatOption);

        rootCommand.SetHandler((reference, target, output, verbose, format) =>
        {
            var result = RunComparison(reference, target, output, verbose, format);
            return Task.FromResult(result);
        }, referenceOption, targetOption, outputOption, verboseOption, formatOption);

        return await rootCommand.InvokeAsync(args);
    }

    static int RunComparison(string referencePath, string targetPath, string? outputPath, bool verbose, string format)
    {
        if (!File.Exists(referencePath))
        {
            Console.Error.WriteLine($"Error: Reference file not found: {referencePath}");
            return 2;
        }

        if (!File.Exists(targetPath))
        {
            Console.Error.WriteLine($"Error: Target file not found: {targetPath}");
            return 2;
        }

        var separator = new string('=', 60);

        if (verbose)
        {
            Console.WriteLine(separator);
            Console.WriteLine("Mesh Comparison Tool");
            Console.WriteLine(separator);
            Console.WriteLine();
        }

        var engine = new MeshComparisonEngine();
        var report = engine.Compare(referencePath, targetPath, verbose);

        // Output results
        if (format.ToLower() == "json")
        {
            var jsonOptions = new JsonSerializerOptions
            {
                WriteIndented = true,
                DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull
            };
            var json = JsonSerializer.Serialize(report, jsonOptions);

            if (!string.IsNullOrEmpty(outputPath))
            {
                File.WriteAllText(outputPath, json);
                if (verbose)
                {
                    Console.WriteLine($"Report written to: {outputPath}");
                }
            }
            else
            {
                Console.WriteLine(json);
            }
        }
        else // summary format
        {
            PrintSummary(report, verbose);
        }

        // Return appropriate exit code
        // 0 = no issues
        // 1 = issues found
        // 2 = error
        if (report.Errors.Count > 0)
        {
            return 2;
        }

        return report.Summary.IssuesFound ? 1 : 0;
    }

    static void PrintSummary(ComparisonReport report, bool verbose)
    {
        var separator = new string('=', 60);

        Console.WriteLine();
        Console.WriteLine(separator);
        Console.WriteLine("COMPARISON SUMMARY");
        Console.WriteLine(separator);
        Console.WriteLine();

        Console.WriteLine($"Reference: {report.Summary.ReferenceFile}");
        Console.WriteLine($"Target:    {report.Summary.TargetFile}");
        Console.WriteLine();

        Console.WriteLine($"Total Bones:      {report.Summary.TotalBones}");
        Console.WriteLine($"Matching Bones:   {report.Summary.MatchingBones}");
        Console.WriteLine($"Issues Found:     {report.Summary.IssuesFound}");
        Console.WriteLine($"Critical Issues:  {report.Summary.CriticalIssues}");
        Console.WriteLine();

        if (report.Diagnosis.InverseBindMatrixIssue)
        {
            Console.WriteLine("DIAGNOSIS:");
            Console.WriteLine($"  Issue Type:     {report.Diagnosis.IssueType}");
            Console.WriteLine($"  Confidence:     {report.Diagnosis.Confidence:P}");
            Console.WriteLine($"  Details:        {report.Diagnosis.Details}");
            Console.WriteLine();
            Console.WriteLine("RECOMMENDATION:");
            Console.WriteLine($"  {report.Diagnosis.Recommendation}");
        }
        else if (report.Summary.IssuesFound)
        {
            Console.WriteLine("DIAGNOSIS:");
            Console.WriteLine($"  Issue Type:     {report.Diagnosis.IssueType}");
            Console.WriteLine($"  {report.Diagnosis.Recommendation}");
        }
        else
        {
            Console.WriteLine("DIAGNOSIS:");
            Console.WriteLine("  All matrices match - no issues detected!");
        }

        if (verbose && report.BoneComparisons.Count > 0)
        {
            Console.WriteLine();
            Console.WriteLine(separator);
            Console.WriteLine("DETAILED BONE COMPARISONS");
            Console.WriteLine(separator);
            Console.WriteLine();

            // Show problematic bones
            var problematicBones = report.BoneComparisons
                .Where(b => b.InverseBindMatrix != null && !b.InverseBindMatrix.Match)
                .Take(10);

            foreach (var bone in problematicBones)
            {
                Console.WriteLine($"Bone: {bone.BoneName}");
                if (bone.InverseBindMatrix != null)
                {
                    Console.WriteLine($"  IBM Error:      {bone.InverseBindMatrix.MaxError:F6}");
                    Console.WriteLine($"  Is Transpose:   {bone.InverseBindMatrix.IsTranspose}");
                    Console.WriteLine($"  Diagnosis:      {bone.InverseBindMatrix.Diagnosis}");
                }
                Console.WriteLine();
            }

            if (report.BoneComparisons.Count(b => b.InverseBindMatrix != null && !b.InverseBindMatrix.Match) > 10)
            {
                Console.WriteLine("... (showing first 10 problematic bones)");
            }
        }

        if (report.Errors.Count > 0)
        {
            Console.WriteLine();
            Console.WriteLine("ERRORS:");
            foreach (var error in report.Errors)
            {
                Console.WriteLine($"  - {error}");
            }
        }

        Console.WriteLine();
        Console.WriteLine(separator);
    }
}
