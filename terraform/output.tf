output "aws_region" {
  description = "AWS region"
  value       = var.aws_region
}

output "ec2_instance_id" {
  description = "EC2 instance ID"
  value       = aws_instance.sde_ec2.id
}

output "ec2_public_ip" {
  description = "EC2 public IP (SSH only; Airflow via ALB)"
  value       = aws_instance.sde_ec2.public_ip
}

output "ec2_public_dns" {
  description = "EC2 public DNS"
  value       = aws_instance.sde_ec2.public_dns
}

output "alb_dns_name" {
  description = "ALB DNS name"
  value       = aws_lb.airflow.dns_name
}

output "alb_arn" {
  description = "ALB ARN"
  value       = aws_lb.airflow.arn
}

output "airflow_url" {
  description = "Airflow URL (ALB or Route53)"
  value       = var.domain_name != "" ? "https://${var.domain_name}" : "http://${aws_lb.airflow.dns_name}"
}

output "waf_web_acl_arn" {
  description = "WAF Web ACL ARN"
  value       = var.enable_waf ? aws_wafv2_web_acl.alb[0].arn : null
}

output "cloudwatch_log_groups" {
  description = "CloudWatch log groups for observability"
  value = {
    airflow = aws_cloudwatch_log_group.airflow_app.name
    system  = aws_cloudwatch_log_group.ec2_system.name
    docker  = aws_cloudwatch_log_group.ec2_docker.name
    waf     = var.enable_waf ? aws_cloudwatch_log_group.waf[0].name : null
  }
}

output "private_key" {
  description = "EC2 private key (sensitive)"
  value       = tls_private_key.custom_key.private_key_pem
  sensitive   = true
}

output "public_key" {
  description = "EC2 public key"
  value       = tls_private_key.custom_key.public_key_openssh
}
