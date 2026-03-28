from logging import getLogger

try:
    import torch
    from torchvision import transforms
    from torchvision.io import read_image
    from torchvision.models.detection import (
        fasterrcnn_resnet50_fpn,
        FasterRCNN_ResNet50_FPN_Weights,
    )
    from transformers import TrOCRProcessor, VisionEncoderDecoderModel
except ImportError as e:
    raise ImportError(
        "OCR requires the 'ocr' extra: uv sync --extra ocr"
    ) from e

logger = getLogger(__name__)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


class Reader:

    def __init__(self):
        self.detector = fasterrcnn_resnet50_fpn(
            weights=FasterRCNN_ResNet50_FPN_Weights.DEFAULT
        ).to(device)
        self.detector.eval()

        self.processor = TrOCRProcessor.from_pretrained("microsoft/trocr-base-printed")
        self.recognizer = VisionEncoderDecoderModel.from_pretrained("microsoft/trocr-base-printed").to(device)

    def extract_image_information(self, image_path: str) -> str:
        """Detect objects/regions in an image and extract text from each crop.

        Returns concatenated recognized text from all detected regions.
        """

        tensor_image, detector_input = self._preprocess_image(image_path)
        crops = self._get_object_crops(tensor_image, detector_input)

        if not crops:
            logger.warning("No regions detected in %s", image_path)
            return ""

        to_pil = transforms.ToPILImage()
        recognized_parts: list[str] = []
        for i, crop in enumerate(crops):
            pil_crop = to_pil(crop)
            pixel_values = self.processor(
                images=pil_crop, return_tensors="pt"
            ).pixel_values.to(device)
            generated_ids = self.recognizer.generate(pixel_values)
            text = self.processor.batch_decode(
                generated_ids, skip_special_tokens=True
            )[0].strip()
            if text:
                recognized_parts.append(text)
            logger.debug("Crop %d: %s", i, text)

        return "\n".join(recognized_parts)

    def _get_object_crops(
        self,
        tensor_image: torch.Tensor,
        detector_input: torch.Tensor,
        score_threshold: float = 0.8,
    ) -> list[torch.Tensor]:
        """Run detection and return cropped regions above the confidence threshold."""
 
        with torch.no_grad():
            preds = self.detector(detector_input)
        logger.debug("Detection output: %s", preds)

        boxes = preds[0]["boxes"]
        scores = preds[0]["scores"]
        confident_boxes = boxes[scores > score_threshold]

        crops = []
        for box in confident_boxes:
            x1, y1, x2, y2 = box.int()
            crop = tensor_image[:, y1:y2, x1:x2]
            crops.append(crop)

        return crops

    def _preprocess_image(
        self, image_path: str
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Load an image and prepare both raw tensor and detector-ready input.

        Returns
        -------
        tuple[torch.Tensor, torch.Tensor]
            (tensor_image [C,H,W] uint8, detector_input [1,C,H,W] float 0-1)
        """
        tensor_image = read_image(image_path).to(device)
        detector_input = (tensor_image.float() / 255.0).unsqueeze(0)
        return tensor_image, detector_input
