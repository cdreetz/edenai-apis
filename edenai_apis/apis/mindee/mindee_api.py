from io import BufferedReader
from collections import defaultdict
from typing import Dict, List, Optional, Sequence, TypeVar, Union
from pydantic import StrictStr
import requests

from edenai_apis.features import ProviderInterface, OcrInterface
from edenai_apis.features.ocr import (
    ReceiptParserDataClass,
    InfosInvoiceParserDataClass,
    InfosReceiptParserDataClass,
    InvoiceParserDataClass,
    IdentityParserDataClass,
    InfosIdentityParserDataClass,
    InfoCountry,
    format_date,
    get_info_country,
    ItemIdentityParserDataClass,
)
from edenai_apis.features.ocr.data_extraction.data_extraction_dataclass import (
    DataExtractionDataClass,
)
from edenai_apis.features.ocr.identity_parser.identity_parser_dataclass import Country
from edenai_apis.features.ocr.invoice_parser.invoice_parser_dataclass import (
    CustomerInformationInvoice,
    LocaleInvoice,
    MerchantInformationInvoice,
    BankInvoice,
    TaxesInvoice,
)
from edenai_apis.features.ocr.receipt_parser.receipt_parser_dataclass import (
    CustomerInformation,
    ItemLines,
    Locale,
    MerchantInformation,
    PaymentInformation,
    Taxes,
)
from edenai_apis.loaders.data_loader import ProviderDataEnum
from edenai_apis.loaders.loaders import load_provider
from edenai_apis.utils.conversion import (
    combine_date_with_time,
    convert_string_to_number,
    from_jsonarray_to_list,
)
from edenai_apis.utils.exception import ProviderException
from edenai_apis.utils.types import ResponseType

ParamsApi = TypeVar("ParamsApi")


class MindeeApi(ProviderInterface, OcrInterface):
    provider_name = "mindee"

    def __init__(self, api_keys: Dict = {}) -> None:
        self.api_settings = load_provider(
            ProviderDataEnum.KEY, self.provider_name, api_keys=api_keys
        )
        self.api_key = self.api_settings["subscription_key"]
        self.url = "https://api.mindee.net/v1/products/mindee/invoices/v3/predict"
        self.url_receipt = (
            "https://api.mindee.net/v1/products/mindee/expense_receipts/v5/predict"
        )
        self.url_identity = (
            "https://api.mindee.net/v1/products/mindee/passport/v1/predict"
        )
        self.url_financial = (
            "https://api.mindee.net/v1/products/mindee/financial_document/v1/predict"
        )

    def _get_api_attributes(
        self, file: BufferedReader, language: Optional[str] = None
    ) -> ParamsApi:
        params: ParamsApi = {
            "headers": {"Authorization": self.api_key},
            "files": {"document": file},
            "params": {
                "local": {
                    "langage": language.split("-")[0],
                    "country": language.split("-")[1],
                }
            }
            if language
            else None,
        }
        return params

    def ocr__receipt_parser(
        self, file: str, language: str, file_url: str = ""
    ) -> ResponseType[ReceiptParserDataClass]:
        file_ = open(file, "rb")
        args = self._get_api_attributes(file_, language)
        original_response = requests.post(
            self.url_receipt,
            headers=args["headers"],
            files=args["files"],
            params=args["params"],
        ).json()

        file_.close()

        if "document" not in original_response:
            raise ProviderException(
                original_response["api_request"]["error"]["message"]
            )

        receipt_data = original_response["document"]["inference"]["prediction"]
        extracted_data = [
            InfosReceiptParserDataClass(
                invoice_number=None,
                invoice_total=receipt_data["total_amount"]["value"],
                invoice_subtotal=None,
                barcodes=[],
                date=combine_date_with_time(
                    receipt_data["date"]["value"], receipt_data["time"]["value"]
                ),
                due_date=None,
                customer_information=CustomerInformation(customer_name=None),
                merchant_information=MerchantInformation(
                    merchant_name=receipt_data["supplier_name"]["value"],
                    merchant_address=receipt_data["supplier_address"]["value"],
                    merchant_phone=receipt_data["supplier_phone_number"]["value"],
                    merchant_url=None,
                    merchant_siret=None,
                    merchant_siren=None,
                ),
                payment_information=PaymentInformation(
                    card_number=None,
                    card_type=None,
                    cash=None,
                    tip=None,
                    change=None,
                    discount=None,
                ),
                locale=Locale(
                    currency=receipt_data["locale"]["currency"],
                    language=receipt_data["locale"]["language"],
                    country=receipt_data["locale"]["country"],
                ),
                taxes=[
                    Taxes(
                        taxes=tax["value"],
                        rate=tax["rate"],
                    )
                    for tax in receipt_data["taxes"]
                ],
                item_lines=[
                    ItemLines(
                        description=item["description"],
                        quantity=item["quantity"],
                        unit_price=item["unit_price"],
                        amount=item["total_amount"],
                    )
                    for item in receipt_data["line_items"]
                ],
            )
        ]

        standardized_response = ReceiptParserDataClass(extracted_data=extracted_data)

        result = ResponseType[ReceiptParserDataClass](
            original_response=original_response,
            standardized_response=standardized_response,
        )
        return result

    def ocr__invoice_parser(
        self, file: str, language: str, file_url: str = ""
    ) -> ResponseType[InvoiceParserDataClass]:
        headers = {
            "Authorization": self.api_key,
        }
        file_ = open(file, "rb")
        files = {"document": file_}
        params = {"locale": {"language": language}}
        original_response = requests.post(
            self.url, headers=headers, files=files, params=params
        ).json()

        file_.close()

        if "document" not in original_response:
            raise ProviderException(
                original_response["api_request"]["error"]["message"]
            )
        # Invoice std :
        invoice_data = original_response["document"]["inference"]["prediction"]
        default_dict = defaultdict(lambda: None)

        # Customer informations
        customer_name = invoice_data.get("customer", default_dict).get("value", None)
        customer_address = invoice_data.get("customer_address", default_dict).get(
            "value", None
        )

        # Merchant information
        merchant_name = invoice_data.get("supplier", default_dict).get("value", None)
        merchant_address = invoice_data.get("supplier_address", default_dict).get(
            "value", None
        )

        # Others
        date = invoice_data.get("date", default_dict).get("value", None)
        time = invoice_data.get("time", default_dict).get("value", None)
        date = combine_date_with_time(date, time)
        invoice_total = convert_string_to_number(
            invoice_data.get("total_incl", default_dict).get("value", None), float
        )
        invoice_subtotal = convert_string_to_number(
            invoice_data.get("total_excl", default_dict).get("value", None), float
        )
        due_date = invoice_data.get("due_date", default_dict).get("value", None)
        due_time = invoice_data.get("due_time", default_dict).get("value", None)
        due_date = combine_date_with_time(due_date, due_time)
        invoice_number = invoice_data.get("invoice_number", default_dict).get(
            "value", None
        )
        taxes: Sequence[TaxesInvoice] = [
            TaxesInvoice(value=item.get("value", None), rate=item["rate"])
            for item in invoice_data.get("taxes", [])
        ]
        currency = invoice_data.get("locale", default_dict)["currency"]
        language = invoice_data.get("locale", default_dict)["language"]

        invoice_parser = InfosInvoiceParserDataClass(
            merchant_information=MerchantInformationInvoice(
                merchant_name=merchant_name,
                merchant_address=merchant_address,
                # Not supported by the Mindee
                # --------------------------------
                merchant_phone=None,
                merchant_email=None,
                merchant_fax=None,
                merchant_website=None,
                merchant_siret=None,
                merchant_siren=None,
                merchant_tax_id=None,
                abn_number=None,
                gst_number=None,
                vat_number=None,
                pan_number=None,
                # --------------------------------
            ),
            customer_information=CustomerInformationInvoice(
                customer_name=customer_name,
                customer_address=customer_address,
                customer_mailing_address=customer_address,
                customer_email=None,
                customer_id=None,
                customer_tax_id=None,
                customer_billing_address=None,
                customer_remittance_address=None,
                customer_service_address=None,
                customer_shipping_address=None,
                abn_number=None,
                gst_number=None,
                pan_number=None,
                vat_number=None,
            ),
            invoice_number=invoice_number,
            invoice_total=invoice_total,
            invoice_subtotal=invoice_subtotal,
            date=date,
            due_date=due_date,
            taxes=taxes,
            locale=LocaleInvoice(currency=currency, language=language),
        )

        standardized_response = InvoiceParserDataClass(extracted_data=[invoice_parser])

        result = ResponseType[InvoiceParserDataClass](
            original_response=original_response,
            standardized_response=standardized_response,
        )
        return result

    def ocr__identity_parser(
        self, file: str, file_url: str = ""
    ) -> ResponseType[IdentityParserDataClass]:
        file_ = open(file, "rb")
        args = self._get_api_attributes(file_)

        response = requests.post(
            url=self.url_identity, files=args["files"], headers=args["headers"]
        )

        file_.close()

        original_response = response.json()
        if response.status_code != 201:
            raise ProviderException(
                message=original_response["api_request"]["error"]["message"],
                code=response.status_code,
            )

        identity_data = original_response["document"]["inference"]["prediction"]

        given_names: Sequence[ItemIdentityParserDataClass] = []

        for given_name in identity_data["given_names"]:
            given_names.append(
                ItemIdentityParserDataClass(
                    value=given_name["value"], confidence=given_name["confidence"]
                )
            )

        last_name = ItemIdentityParserDataClass(
            value=identity_data["surname"]["value"],
            confidence=identity_data["surname"]["confidence"],
        )
        birth_date = ItemIdentityParserDataClass(
            value=identity_data["birth_date"]["value"],
            confidence=identity_data["birth_date"]["confidence"],
        )
        birth_place = ItemIdentityParserDataClass(
            value=identity_data["birth_place"]["value"],
            confidence=identity_data["birth_place"]["confidence"],
        )

        country: Country = get_info_country(
            key=InfoCountry.ALPHA3, value=identity_data["country"]["value"]
        )
        if country:
            country["confidence"] = identity_data["country"]["confidence"]

        issuance_date = ItemIdentityParserDataClass(
            value=identity_data["issuance_date"]["value"],
            confidence=identity_data["issuance_date"]["confidence"],
        )
        expire_date = ItemIdentityParserDataClass(
            value=identity_data["expiry_date"]["value"],
            confidence=identity_data["expiry_date"]["confidence"],
        )
        document_id = ItemIdentityParserDataClass(
            value=identity_data["id_number"]["value"],
            confidence=identity_data["id_number"]["confidence"],
        )
        gender = ItemIdentityParserDataClass(
            value=identity_data["gender"]["value"],
            confidence=identity_data["gender"]["confidence"],
        )
        mrz = ItemIdentityParserDataClass(
            value=identity_data["mrz1"]["value"],
            confidence=identity_data["mrz1"]["confidence"],
        )
        items: Sequence[InfosIdentityParserDataClass] = []
        items.append(
            InfosIdentityParserDataClass(
                last_name=last_name,
                given_names=given_names,
                birth_date=birth_date,
                birth_place=birth_place,
                country=country or Country.default(),
                issuance_date=issuance_date,
                expire_date=expire_date,
                document_id=document_id,
                gender=gender,
                mrz=mrz,
                image_id=[],
                issuing_state=ItemIdentityParserDataClass(),
                address=ItemIdentityParserDataClass(),
                age=ItemIdentityParserDataClass(),
                document_type=ItemIdentityParserDataClass(),
                nationality=ItemIdentityParserDataClass(),
                image_signature=[],
            )
        )

        standardized_response = IdentityParserDataClass(extracted_data=items)

        return ResponseType[IdentityParserDataClass](
            original_response=original_response,
            standardized_response=standardized_response,
        )
