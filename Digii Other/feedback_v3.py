import pandas as pd
from typing import Dict, List, Optional, Tuple
import numpy as np

class FeedbackAnalyzer:
    """
    Efficient feedback analysis class that calculates aggregations dynamically
    """
    
    def __init__(self, feedback_data: pd.DataFrame, class_students_data: pd.DataFrame):
        """
        Initialize with feedback and class students data
        
        Args:
            feedback_data: Raw feedback data
            class_students_data: Class-student mapping data
        """
        self.feedback = self._normalize_columns(feedback_data)
        self.class_students = self._normalize_columns(class_students_data)
        self._consolidated_full = None
        self._question_level_report = None
        
    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize column names to lowercase with stripped whitespace"""
        df = df.copy()
        df.columns = [c.strip().lower() for c in df.columns]
        return df
    
    def get_consolidated_data(self) -> pd.DataFrame:
        """Get consolidated data with respondents and non-respondents"""
        if self._consolidated_full is None:
            self._consolidated_full = self._create_consolidated_data()
        return self._consolidated_full
    
    def _create_consolidated_data(self) -> pd.DataFrame:
        """Create consolidated dataset with both respondents and non-respondents"""
        # Step 1: Consolidate respondents
        consolidated = self.feedback.groupby([
            'session_name', 'term', 'programme_name', 'course_code', 'course_name',
            'type', 'class_id', 'batch', 'faculty_name', 'faculty_ukid', 'template_name',
            'student_ukid', 'session_id', 'template_id'
        ]).agg(
            submitted=('submitted', 'max'),
            avg_score=('option_score', 'mean'),
            response_status=('response_status', 'first'),
            report_published=('report_published', 'first')
        ).reset_index()
        consolidated['avg_score'] = consolidated['avg_score'].round(2)
        
        # Step 2: Add non-respondents
        non_respondents = self._get_non_respondents()
        
        # Step 3: Combine and add question counts
        full_data = pd.concat([consolidated, non_respondents], ignore_index=True)
        question_counts = self._get_question_counts()
        
        return full_data.merge(question_counts, on=[
            'class_id', 'session_id', 'course_code', 'faculty_ukid', 'template_id'
        ], how='left')
    
    def _get_non_respondents(self) -> pd.DataFrame:
        """Identify and create records for non-respondents"""
        # Get unique teaching instances
        teaching_instances = self.feedback[[
            'class_id', 'session_id', 'course_code', 'faculty_ukid', 'template_id'
        ]].drop_duplicates()
        
        # Get expected responses
        expected_responses = teaching_instances.merge(self.class_students, on='class_id', how='left')
        
        # Get actual responses
        actual_responses = self.feedback.groupby([
            'class_id', 'student_ukid', 'session_id', 'course_code', 'faculty_ukid', 'template_id'
        ])['submitted'].max().reset_index()
        
        # Find non-respondents
        merged = expected_responses.merge(
            actual_responses,
            on=['class_id', 'student_ukid', 'session_id', 'course_code', 'faculty_ukid', 'template_id'],
            how='left'
        )
        
        non_respondents = merged[merged['submitted'].isna()].copy()
        
        # Add metadata
        metadata = self.feedback.groupby([
            'class_id', 'session_id', 'course_code', 'faculty_ukid', 'template_id'
        ]).first().reset_index()
        
        non_respondents = non_respondents.merge(
            metadata[['class_id', 'session_id', 'course_code', 'faculty_ukid', 'template_id',
                     'session_name', 'term', 'programme_name', 'course_name', 'type', 'batch',
                     'faculty_name', 'template_name', 'report_published']],
            on=['class_id', 'session_id', 'course_code', 'faculty_ukid', 'template_id'],
            how='left'
        )
        
        # Fill non-respondent fields
        non_respondents['submitted'] = 0
        non_respondents['avg_score'] = None
        non_respondents['response_status'] = "Not Responded"
        
        return non_respondents
    
    def _get_question_counts(self) -> pd.DataFrame:
        """Get number of questions per teaching instance"""
        return (self.feedback.groupby([
            'class_id', 'session_id', 'course_code', 'faculty_ukid', 'template_id'
        ])['question_id'].nunique().reset_index(name='num_questions'))
    
    def calculate_aggregation(self, group_cols: List[str], 
                            score_col: str = 'option_score',
                            include_participation: bool = True) -> pd.DataFrame:
        """
        Dynamically calculate aggregations for any grouping level
        
        Args:
            group_cols: Columns to group by
            score_col: Score column to aggregate
            include_participation: Whether to include participation metrics
            
        Returns:
            DataFrame with aggregated metrics
        """
        # Get consolidated data
        consolidated = self.get_consolidated_data()
        
        # Calculate average scores
        result = self.feedback.groupby(group_cols)[score_col].agg([
            ('avg_score', 'mean'),
            ('max_score', 'max'),
            ('min_score', 'min'),
            ('std_score', 'std'),
            ('response_count', 'count')
        ]).reset_index()
        
        # Normalize scores to 10-point scale
        result['avg_score_normalized'] = (
            (result['avg_score'] / result['max_score']) * 10
        ).round(2)
        
        # Round scores
        result['avg_score'] = result['avg_score'].round(2)
        result['std_score'] = result['std_score'].round(2)
        
        if include_participation:
            # Add participation metrics
            participation = consolidated.groupby(group_cols)['submitted'].agg([
                ('participants', 'sum'),
                ('expected', 'count')
            ]).reset_index()
            
            participation['participation_%'] = (
                (participation['participants'] / participation['expected']) * 100
            ).round(2)
            
            result = result.merge(participation, on=group_cols, how='left')
        
        return result
    
    def get_question_level_report(self) -> pd.DataFrame:
        """Get detailed question-level report with all aggregation levels"""
        if self._question_level_report is None:
            self._question_level_report = self._create_question_level_report()
        return self._question_level_report
    
    def _create_question_level_report(self) -> pd.DataFrame:
        """Create comprehensive question-level report"""
        # Base question-option counts
        question_option_counts = self.feedback.groupby([
            'session_name', 'term', 'course_code', 'class_id', 'faculty_name', 'template_name',
            'question_id', 'question_text', 'option_text'
        ]).agg(
            response_count=('student_ukid', 'nunique'),
            avg_score_option=('option_score', 'mean')
        ).reset_index()
        
        # Add question-level scores
        question_scores = self.calculate_aggregation([
            'session_name', 'term', 'course_code', 'class_id', 'faculty_name', 'template_name',
            'question_id'
        ], include_participation=False)
        
        # Add template-level scores
        template_scores = self.calculate_aggregation([
            'session_name', 'term', 'course_code', 'class_id', 'faculty_name', 'template_name'
        ])
        
        # Add faculty-level scores
        faculty_scores = self.calculate_aggregation([
            'session_name', 'faculty_name', 'term'
        ])
        
        # Add course-level scores
        course_scores = self.calculate_aggregation([
            'session_name', 'course_code', 'term'
        ])
        
        # Add class-level scores
        class_scores = self.calculate_aggregation([
            'session_name', 'class_id', 'term'
        ])
        
        # Merge all levels
        result = (question_option_counts
                 .merge(question_scores, on=[
                     'session_name', 'term', 'course_code', 'class_id', 'faculty_name', 'template_name',
                     'question_id'
                 ], how='left')
                 .merge(template_scores, on=[
                     'session_name', 'term', 'course_code', 'class_id', 'faculty_name', 'template_name'
                 ], how='left', suffixes=('_question', '_template'))
                 .merge(faculty_scores, on=['session_name', 'faculty_name', 'term'], how='left')
                 .merge(course_scores, on=['session_name', 'course_code', 'term'], how='left')
                 .merge(class_scores, on=['session_name', 'class_id', 'term'], how='left'))
        
        # Add high satisfaction percentage
        result = self._add_high_satisfaction(result)
        
        # Round scores
        score_cols = ['avg_score_option', 'avg_score_question', 'avg_score_template', 
                     'avg_score_faculty', 'avg_score_course', 'avg_score_class']
        for col in score_cols:
            if col in result.columns:
                result[col] = result[col].round(2)
        
        return result.sort_values([
            'session_name', 'term', 'course_code', 'class_id', 'question_id', 'option_text'
        ])
    
    def _add_high_satisfaction(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add high satisfaction percentage to the dataframe"""
        # Calculate normalized scores for high satisfaction
        high_sat = self.feedback.copy()
        
        # Get max scores per template
        max_scores = self.feedback.groupby([
            'class_id', 'session_id', 'course_code', 'faculty_ukid', 'template_id'
        ])['option_score'].max().reset_index(name='max_option_score')
        
        high_sat = high_sat.merge(max_scores, on=[
            'class_id', 'session_id', 'course_code', 'faculty_ukid', 'template_id'
        ], how='left')
        
        high_sat['normalized_score'] = high_sat['option_score'] / high_sat['max_option_score']
        
        # Calculate high satisfaction percentage
        high_sat_pct = high_sat.groupby([
            'session_name', 'term', 'course_code', 'class_id', 'faculty_name', 'template_name',
            'question_id'
        ]).apply(lambda x: round((x['normalized_score'] >= 0.8).sum() / len(x) * 100, 2)).reset_index(name='high_sat_%')
        
        return df.merge(high_sat_pct, on=[
            'session_name', 'term', 'course_code', 'class_id', 'faculty_name', 'template_name',
            'question_id'
        ], how='left')
    
    def get_dashboard_summary(self) -> Dict[str, pd.DataFrame]:
        """
        Get summary data for dashboard - calculates only what's needed
        
        Returns:
            Dictionary with different dashboard views
        """
        consolidated = self.get_consolidated_data()
        
        return {
            'faculty_summary': self.calculate_aggregation(['session_name', 'faculty_name', 'term']),
            'course_summary': self.calculate_aggregation(['session_name', 'course_code', 'term']),
            'class_summary': self.calculate_aggregation(['session_name', 'class_id', 'term']),
            'template_summary': self.calculate_aggregation([
                'session_name', 'term', 'course_code', 'class_id', 'faculty_name', 'template_name'
            ]),
            'overall_summary': self.calculate_aggregation(['session_name', 'term']),
            'participation_summary': consolidated.groupby(['session_name', 'term']).agg({
                'submitted': ['sum', 'count']
            }).round(2)
        }
    
    def export_to_excel(self, output_path: str):
        """Export results to Excel file"""
        with pd.ExcelWriter(output_path) as writer:
            # Export consolidated data
            self.get_consolidated_data().to_excel(
                writer, sheet_name="Consolidated Report", index=False
            )
            
            # Export question level report
            self.get_question_level_report().to_excel(
                writer, sheet_name="Question Level Report", index=False
            )
            
            # Export dashboard summaries
            dashboard_data = self.get_dashboard_summary()
            for name, data in dashboard_data.items():
                data.to_excel(writer, sheet_name=name.replace('_', ' ').title(), index=False)
        
        print(f"✅ Excel file generated: {output_path}")

# ---------------------------
# Usage Example
# ---------------------------

def main():
    """Main function to run the analysis"""
    # Load data
    feedback = pd.read_csv(r"C:\Users\Suraj Shetty\OneDrive\Desktop\MAB sess 1 6 254 feedback raw.csv")
    class_students = pd.read_csv(r"C:\Users\Suraj Shetty\OneDrive\Desktop\mab session 6 feedback class_student.csv")
    
    # Initialize analyzer
    analyzer = FeedbackAnalyzer(feedback, class_students)
    
    # Export results
    output_path = r"C:\Users\Suraj Shetty\OneDrive\Desktop\feedback_summary_v2_efficient.xlsx"
    analyzer.export_to_excel(output_path)
    
    # Example: Get specific aggregations for dashboard
    faculty_summary = analyzer.calculate_aggregation(['session_name', 'faculty_name', 'term'])
    course_summary = analyzer.calculate_aggregation(['session_name', 'course_code', 'term'])
    
    print("✅ Analysis completed!")
    print(f"📊 Faculty summary shape: {faculty_summary.shape}")
    print(f"📊 Course summary shape: {course_summary.shape}")

if __name__ == "__main__":
    main()
